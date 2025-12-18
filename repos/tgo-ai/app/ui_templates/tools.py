"""
UI Template Tools for LLM Function Calling.

This module provides tools that allow LLMs to discover and use UI templates
through function calling, implementing the two-phase loading strategy.
"""

import json
from typing import Any, Dict

from pydantic import ValidationError

from app.ui_templates.registry import UITemplateRegistry
from app.ui_templates.prompt_builder import generate_template_detail
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_ui_template(template_name: str) -> str:
    """获取指定 UI 模板的详细 schema 格式和使用示例。
    
    当用户请求展示结构化信息（如订单详情、产品介绍、物流状态等）时，你**必须首先调用此工具**来了解该模板所需的具体字段结构和数据类型。
    调用后，你将获得一个 JSON 格式的模板说明，请严格按照该说明组织数据。

    Args:
        template_name: 模板名称。可选值:
            - 'order': 订单详情（单号、金额、商品列表等）
            - 'product': 单个产品详情（名称、图片、价格、规格等）
            - 'product_list': 产品列表/搜索结果
            - 'logistics': 物流跟踪信息
            - 'price_comparison': 价格对比表

    Returns:
        包含字段定义、数据类型、必填项说明以及完整示例的文档。
    """
    logger.info(f"Getting UI template: {template_name}")
    return generate_template_detail(template_name)


def render_ui(template_name: str, data: Dict[str, Any]) -> str:
    """将业务数据渲染为前端可识别的 UI 组件代码块。

    在获取了模板格式（通过 get_ui_template）并准备好数据后，调用此工具生成最终的 Markdown 代码块。
    返回的内容是一个包含 `tgo-ui-widget` 标识的 Markdown 块，你应当将其直接包含在回复给用户的消息中。

    注意：
    1. 确保 data 中的字段完全符合模板定义。
    2. 数值型字段（如价格、数量）请传数字而非字符串。
    3. 如果数据验证失败，此工具会返回具体的错误原因，请根据错误修正后重试。

    Args:
        template_name: 模板名称 (需与 data 中的 type 一致)
        data: 符合模板定义的 JSON 数据对象。

    Returns:
        格式化的 Markdown 代码块（如 ```tgo-ui-widget ... ```）或验证错误信息。
    """
    logger.info(f"Rendering UI template: {template_name}")

    template_cls = UITemplateRegistry.get_template(template_name)
    if template_cls is None:
        available = ", ".join(UITemplateRegistry.list_template_types())
        return f"错误：未知模板 '{template_name}'。可用模板: {available}"

    try:
        # Ensure type field is set correctly
        data["type"] = template_name

        # Validate and create instance
        instance = template_cls(**data)

        # Return formatted markdown
        return instance.to_markdown()

    except ValidationError as e:
        error_details = []
        for error in e.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            error_details.append(f"  - {field}: {msg}")

        return f"数据格式错误:\n" + "\n".join(error_details)

    except Exception as e:
        logger.error(f"Failed to render template {template_name}: {e}")
        return f"渲染错误: {str(e)}"


def list_ui_templates() -> str:
    """
    列出所有可用的 UI 模板。

    Returns:
        可用模板列表及其简短描述
    """
    templates = UITemplateRegistry.get_all_templates()

    if not templates:
        return "暂无可用的 UI 模板"

    lines = ["可用的 UI 模板:\n"]

    for template_type, template_cls in templates.items():
        description = template_cls.get_description()
        lines.append(f"- **{template_type}**: {description}")

    return "\n".join(lines)


def validate_ui_data(template_name: str, data: Dict[str, Any]) -> str:
    """
    验证数据是否符合指定模板的格式要求。

    Args:
        template_name: 模板名称
        data: 要验证的数据

    Returns:
        验证结果（成功或错误详情）
    """
    is_valid, error_msg = UITemplateRegistry.validate_data(template_name, data)

    if is_valid:
        return "✓ 数据格式正确"
    else:
        return f"✗ 数据格式错误: {error_msg}"


# Tool definitions for OpenAI-compatible function calling format
UI_TEMPLATE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_ui_template",
            "description": "获取指定 UI 模板的详细 schema 格式和使用示例。当需要展示订单、产品、物流等结构化数据时，必须先调用此工具获取格式要求。",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "模板名称，可选值: order, product, product_list, logistics, price_comparison",
                        "enum": ["order", "product", "product_list", "logistics", "price_comparison"],
                    }
                },
                "required": ["template_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "render_ui",
            "description": "将业务数据渲染为前端可识别的 UI 组件代码块 (tgo-ui-widget)。调用前请确保已通过 get_ui_template 了解格式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "模板名称",
                        "enum": ["order", "product", "product_list", "logistics", "price_comparison"],
                    },
                    "data": {
                        "type": "object",
                        "description": "要渲染的 JSON 数据对象，需符合模板定义的格式要求",
                    },
                },
                "required": ["template_name", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_ui_templates",
            "description": "列出所有可用的 UI 模板及其简短描述，用于快速了解有哪些可用展示组件。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# Function mapping for tool execution
UI_TEMPLATE_TOOL_FUNCTIONS = {
    "get_ui_template": get_ui_template,
    "render_ui": render_ui,
    "list_ui_templates": list_ui_templates,
    "validate_ui_data": validate_ui_data,
}


def execute_ui_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Execute a UI template tool by name.

    Args:
        tool_name: Name of the tool to execute.
        arguments: Arguments to pass to the tool.

    Returns:
        Tool execution result.
    """
    func = UI_TEMPLATE_TOOL_FUNCTIONS.get(tool_name)
    if func is None:
        return f"未知工具: {tool_name}"

    try:
        return func(**arguments)
    except Exception as e:
        logger.error(f"Error executing UI tool {tool_name}: {e}")
        return f"工具执行错误: {str(e)}"
