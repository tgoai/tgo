"""MCP Tool Agent - Agent that uses device as MCP remote tool provider.

This module implements an agent that:
1. Loads available tools from the connected device via tools/list
2. Converts MCP tool definitions to OpenAI Function Calling format
3. Uses LLM (via tgo-ai service) to autonomously decide which tools to call
4. Executes tools via tools/call and analyzes results
5. Continues until task completion or max iterations reached
"""

import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import uuid4

import httpx
from pydantic import BaseModel

from app.config import settings
from app.core.logging import get_logger
from app.schemas.agent_events import AgentEvent, AgentEventType
from app.services.tcp_connection_manager import (
    TcpDeviceConnection,
    tcp_connection_manager,
)

logger = get_logger("services.computer_use.mcp_agent")


# System prompt for the MCP Agent
AGENT_SYSTEM_PROMPT = """You are a Computer Use Agent that controls a device to complete tasks.

## Your Capabilities
You can control the device using the available tools provided by the connected device.
Each tool has specific parameters - use them according to their descriptions.

## Workflow
1. **Observe**: Use 'see' or 'image' tool to capture the current screen state
2. **Analyze**: Look at the screenshot and understand what's displayed
3. **Act**: Use appropriate tools (click, type, scroll, etc.) to interact with the UI
4. **Verify**: Take another screenshot to verify the action succeeded
5. **Repeat**: Continue until the task is complete

## Important Guidelines
- Always start by taking a screenshot to see the current state
- After each action, take another screenshot to verify the result
- Use element queries when possible (e.g., click on "Submit button")
- Use coordinates only when element queries don't work
- If an action fails, try alternative approaches
- When the task is complete, respond with a final summary message without calling any tools

## Response Format
- When you need to perform an action, call the appropriate tool
- When the task is complete, respond with a text message summarizing what was accomplished
- If you encounter an error you cannot resolve, explain the issue clearly
"""


class McpAgent:
    """Agent that uses device as MCP remote tool provider.

    This agent:
    1. Connects to a device and loads its available tools
    2. Converts tools to OpenAI Function Calling format
    3. Uses LLM to decide which tools to call
    4. Executes tools and analyzes results
    5. Continues until task completion or max iterations
    """

    def __init__(
        self,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        project_id: Optional[str] = None,
        max_iterations: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ):
        """Initialize the MCP Agent.

        Args:
            provider_id: AI Provider ID for LLM calls via tgo-ai service.
            model: LLM model to use (default: settings.AGENT_MODEL).
            project_id: Project ID for authorization.
            max_iterations: Max iterations (default: settings.AGENT_MAX_ITERATIONS).
            system_prompt: Custom system prompt (default: AGENT_SYSTEM_PROMPT).
        """
        self.provider_id = provider_id
        self.model = model or settings.AGENT_MODEL
        self.project_id = project_id
        self.max_iterations = max_iterations or settings.AGENT_MAX_ITERATIONS
        self.system_prompt = (
            system_prompt or settings.AGENT_SYSTEM_PROMPT or AGENT_SYSTEM_PROMPT
        )

        # State
        self._device_tools: List[Dict[str, Any]] = []
        self._openai_tools: List[Dict[str, Any]] = []
        self._messages: List[Dict[str, Any]] = []

        logger.info(
            f"McpAgent initialized with model: {self.model}, "
            f"provider_id: {self.provider_id}, project_id: {self.project_id}"
        )

    async def load_device_tools(
        self, connection: TcpDeviceConnection
    ) -> List[Dict[str, Any]]:
        """Load available tools from the device.

        Args:
            connection: TCP device connection.

        Returns:
            List of MCP tool definitions.

        Raises:
            RuntimeError: If tools cannot be loaded.
        """
        logger.info(f"Loading tools from device: {connection.agent_id}")

        tools = await connection.list_tools()
        if tools is None:
            raise RuntimeError(
                f"Failed to load tools from device {connection.agent_id}"
            )

        self._device_tools = tools
        self._openai_tools = self._convert_to_openai_functions(tools)

        logger.info(f"Loaded {len(tools)} tools from device")
        return tools

    def _convert_to_openai_functions(
        self, mcp_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert MCP tool definitions to OpenAI Function Calling format.

        Args:
            mcp_tools: List of MCP tool definitions.

        Returns:
            List of OpenAI function definitions.
        """
        openai_tools = []

        for tool in mcp_tools:
            name = tool.get("name", "")
            description = tool.get("description", "")
            input_schema = tool.get("inputSchema", {})

            # Convert to OpenAI format
            openai_tool = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": input_schema,
                },
            }
            openai_tools.append(openai_tool)

        return openai_tools

    async def run(
        self,
        task: str,
        device_id: str,
    ) -> AsyncGenerator[AgentEvent, None]:
        """Run the agent to complete a task.

        Args:
            task: Task description to complete.
            device_id: ID of the device to control.

        Yields:
            AgentEvent objects for each step of execution.
        """
        run_id = str(uuid4())

        # Emit started event
        yield AgentEvent.started(
            run_id=run_id,
            task=task,
            max_iterations=self.max_iterations,
            device_id=device_id,
        )

        # Get device connection
        connection = tcp_connection_manager.get_connection(device_id)
        if not connection:
            yield AgentEvent.create_error(
                run_id=run_id,
                error_message=f"Device {device_id} is not connected",
                error_code="DEVICE_NOT_CONNECTED",
            )
            return

        # Load device tools
        try:
            tools = await self.load_device_tools(connection)
            tool_names = [t.get("name", "") for t in tools]
            yield AgentEvent.tools_loaded(
                run_id=run_id,
                tool_count=len(tools),
                tool_names=tool_names,
            )
        except Exception as e:
            yield AgentEvent.create_error(
                run_id=run_id,
                error_message=str(e),
                error_code="TOOLS_LOAD_FAILED",
            )
            return

        # Initialize messages with system prompt and task
        self._messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": task},
        ]

        # Main agent loop
        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"Agent iteration {iteration}/{self.max_iterations}")

            try:
                # Call LLM
                yield AgentEvent.thinking(
                    run_id=run_id,
                    iteration=iteration,
                    max_iterations=self.max_iterations,
                )

                response = await self._call_llm()

                # Get the assistant message from response dict
                choices = response.get("choices", [])
                if not choices:
                    raise RuntimeError("No choices in LLM response")

                assistant_message = choices[0].get("message", {})
                tool_calls = assistant_message.get("tool_calls", [])

                # Check if task is complete (no tool calls)
                if not tool_calls:
                    # Task complete - emit final result
                    final_content = assistant_message.get("content") or "Task completed"
                    yield AgentEvent.completed(
                        run_id=run_id,
                        final_result=final_content,
                        iteration=iteration,
                    )
                    return

                # Add assistant message to history
                self._messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.get("content"),
                        "tool_calls": [
                            {
                                "id": tc.get("id"),
                                "type": "function",
                                "function": {
                                    "name": tc.get("function", {}).get("name"),
                                    "arguments": tc.get("function", {}).get("arguments", "{}"),
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                # Execute each tool call
                for tool_call in tool_calls:
                    tool_name = tool_call.get("function", {}).get("name", "")
                    try:
                        tool_args = json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                    except json.JSONDecodeError:
                        tool_args = {}

                    # Emit tool call event
                    yield AgentEvent.create_tool_call(
                        run_id=run_id,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        iteration=iteration,
                    )

                    # Execute tool
                    result = await self._execute_tool(connection, tool_name, tool_args)

                    # Emit tool result event
                    yield AgentEvent.create_tool_result(
                        run_id=run_id,
                        tool_name=tool_name,
                        result=result,
                        iteration=iteration,
                    )

                    # Add tool result to messages
                    self._messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.get("id"),
                            "content": self._format_tool_result(result),
                        }
                    )

            except Exception as e:
                logger.exception(f"Agent iteration error: {e}")
                yield AgentEvent.create_error(
                    run_id=run_id,
                    error_message=str(e),
                    error_code="ITERATION_ERROR",
                    iteration=iteration,
                )
                return

        # Max iterations reached
        yield AgentEvent.create_error(
            run_id=run_id,
            error_message=f"Max iterations ({self.max_iterations}) reached without completing task",
            error_code="MAX_ITERATIONS_EXCEEDED",
            iteration=self.max_iterations,
        )

    async def _call_llm(self) -> Dict[str, Any]:
        """Call the LLM via tgo-ai service.

        Returns:
            ChatCompletion response from the LLM (as dict).

        Raises:
            RuntimeError: If provider_id or project_id is not configured.
            httpx.HTTPStatusError: If the API call fails.
        """
        if not self.provider_id or not self.project_id:
            raise RuntimeError(
                "provider_id and project_id are required for LLM calls. "
                "Please configure device control model in settings."
            )

        # Prepare messages for LLM (handle images in tool results)
        messages = self._prepare_messages_for_llm()

        payload: Dict[str, Any] = {
            "provider_id": self.provider_id,
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": 0.1,
            "stream": False,
            # Disable tgo-ai's internal agentic loop so tool_calls are returned as-is.
            # The mcp_agent handles tool execution on the device itself.
            "auto_execute_tools": False,
        }

        # Only include tools if available
        if self._openai_tools:
            payload["tools"] = self._openai_tools
            payload["tool_choice"] = "auto"

        logger.debug(f"Calling tgo-ai service: model={self.model}, messages={len(messages)}")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.AI_SERVICE_URL}/api/v1/chat/completions",
                params={"project_id": self.project_id},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def _prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
        """Prepare messages for LLM, converting images to proper format.

        Returns:
            List of messages formatted for the LLM.
        """
        prepared = []

        for msg in self._messages:
            if msg["role"] == "tool":
                # Check if tool result contains image data
                content = msg.get("content", "")
                if isinstance(content, str) and content.startswith("[IMAGE:"):
                    # Extract base64 image data
                    # Format: [IMAGE:base64_data]
                    image_data = content[7:-1]  # Remove [IMAGE: and ]
                    prepared.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Tool result (tool_call_id: {msg.get('tool_call_id', 'unknown')}):",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_data}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    )
                else:
                    prepared.append(msg)
            else:
                prepared.append(msg)

        return prepared

    async def _execute_tool(
        self,
        connection: TcpDeviceConnection,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a tool on the device.

        Args:
            connection: TCP device connection.
            tool_name: Name of the tool to execute.
            tool_args: Arguments for the tool.

        Returns:
            Tool execution result.
        """
        logger.info(f"Executing tool: {tool_name} with args: {tool_args}")

        result = await connection.call_tool(tool_name, tool_args)

        if result is None:
            return {"error": "Tool call timed out", "isError": True}

        return result

    def _format_tool_result(self, result: Dict[str, Any]) -> str:
        """Format tool result for adding to messages.

        Args:
            result: Raw tool result from device.

        Returns:
            Formatted string representation of the result.
        """
        # Check for errors
        if result.get("isError") or result.get("error"):
            error_msg = "Tool execution failed"
            content = result.get("content", [])
            for item in content:
                if item.get("type") == "text":
                    error_msg = item.get("text", error_msg)
                    break
            if isinstance(result.get("error"), dict):
                error_msg = result["error"].get("message", error_msg)
            elif isinstance(result.get("error"), str):
                error_msg = result["error"]
            return f"Error: {error_msg}"

        # Process content array
        content = result.get("content", [])
        parts = []

        for item in content:
            item_type = item.get("type", "")

            if item_type == "text":
                parts.append(item.get("text", ""))
            elif item_type == "image":
                # Return special marker for image data
                image_data = item.get("data", "")
                if image_data:
                    return f"[IMAGE:{image_data}]"

        if parts:
            return "\n".join(parts)

        # Fallback: return raw result as JSON
        return json.dumps(result)


# Factory function for creating agent instances
def create_mcp_agent(
    provider_id: Optional[str] = None,
    model: Optional[str] = None,
    project_id: Optional[str] = None,
    max_iterations: Optional[int] = None,
    system_prompt: Optional[str] = None,
) -> McpAgent:
    """Create a new McpAgent instance.

    Args:
        provider_id: AI Provider ID for LLM calls.
        model: LLM model to use.
        project_id: Project ID for authorization.
        max_iterations: Maximum iterations.
        system_prompt: Custom system prompt.

    Returns:
        Configured McpAgent instance.
    """
    return McpAgent(
        provider_id=provider_id,
        model=model,
        project_id=project_id,
        max_iterations=max_iterations,
        system_prompt=system_prompt,
    )
