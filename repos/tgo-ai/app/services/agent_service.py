"""Agent service for business logic."""

import uuid
from typing import List, Optional, Tuple, Dict

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import NotFoundError, ValidationError
from app.models.agent import Agent, AgentToolAssociation
from app.models.collection import AgentCollection
from app.models.workflow import AgentWorkflow
from app.models.tool import Tool

from app.models.team import Team
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.rag_service import rag_service_client
from app.services.workflow_service import workflow_service_client


class AgentService:
    """Service for agent-related business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_agent(self, project_id: uuid.UUID, agent_data: AgentCreate) -> Agent:
        """
        Create a new agent.

        Args:
            project_id: Project ID
            agent_data: Agent creation data

        Returns:
            Created agent

        Raises:
            NotFoundError: If team not found
            ValidationError: If team belongs to different project or tools not found
        """
        # Validate team if provided
        if agent_data.team_id:
            await self._validate_team_belongs_to_project(agent_data.team_id, project_id)

        # Validate tools if provided
        if agent_data.tools:
            tool_ids = [tool.tool_id for tool in agent_data.tools]
            await self._validate_tools_belong_to_project(tool_ids, project_id)

        # Create agent
        agent = Agent(
            project_id=project_id,
            team_id=agent_data.team_id,
            llm_provider_id=agent_data.llm_provider_id,
            name=agent_data.name,
            instruction=agent_data.instruction,
            model=agent_data.model,
            is_default=agent_data.is_default,
            is_remote_store_agent=agent_data.is_remote_store_agent,
            remote_agent_url=agent_data.remote_agent_url,
            store_agent_id=agent_data.store_agent_id,
            config=agent_data.config,
            bound_device_id=agent_data.bound_device_id,
        )

        self.db.add(agent)
        await self.db.flush()  # Get agent ID

        # Create tool associations (many-to-many)
        if agent_data.tools:
            for tool_binding in agent_data.tools:
                association = AgentToolAssociation(
                    agent_id=agent.id,
                    tool_id=tool_binding.tool_id,
                    enabled=tool_binding.enabled,
                    permissions=tool_binding.permissions,
                    config=tool_binding.config,
                )
                self.db.add(association)

        # Create collection bindings
        if agent_data.collections:
            for collection_id_str in agent_data.collections:
                agent_collection = AgentCollection(
                    agent_id=agent.id,
                    collection_id=collection_id_str,
                )
                self.db.add(agent_collection)

        # Create workflow bindings
        if agent_data.workflows:
            for workflow_id_str in agent_data.workflows:
                agent_workflow = AgentWorkflow(
                    agent_id=agent.id,
                    workflow_id=workflow_id_str,
                )
                self.db.add(agent_workflow)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_agent(self, project_id: uuid.UUID, agent_id: uuid.UUID) -> Agent:
        """
        Get an agent by ID.

        Args:
            project_id: Project ID
            agent_id: Agent ID

        Returns:
            Agent

        Raises:
            NotFoundError: If agent not found
        """
        stmt = (
            select(Agent)
            .options(
                selectinload(Agent.tools),
                selectinload(Agent.collections),
                selectinload(Agent.workflows),
                selectinload(Agent.team),
                selectinload(Agent.llm_provider),
            )
            .where(
                and_(
                    Agent.id == agent_id,
                    Agent.project_id == project_id,
                    Agent.deleted_at.is_(None),
                )
            )
        )
        result = await self.db.execute(stmt)
        agent = result.scalar_one_or_none()

        if not agent:
            raise NotFoundError("Agent", agent_id)

        # Enrich agent with collection data, workflow data, and tool details
        enriched_agents = await self.enrich_agents_with_collection_data([agent], project_id)
        enriched_agents = await self.enrich_agents_with_workflow_data(enriched_agents, project_id)
        enriched_agents = await self.enrich_agents_with_tool_details(enriched_agents, project_id)
        return enriched_agents[0]

    async def list_agents(
        self,
        project_id: uuid.UUID,
        team_id: Optional[uuid.UUID] = None,
        model: Optional[str] = None,
        is_default: Optional[bool] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Agent], int]:
        """
        List agents for a project.

        Args:
            project_id: Project ID
            team_id: Filter by team ID
            model: Filter by model
            is_default: Filter by default status
            limit: Number of agents to return
            offset: Number of agents to skip

        Returns:
            Tuple of (agents, total_count)
        """
        # Build base query
        conditions = [
            Agent.project_id == project_id,
            Agent.deleted_at.is_(None),
        ]

        if team_id is not None:
            conditions.append(Agent.team_id == team_id)
        if model is not None:
            conditions.append(Agent.model == model)
        if is_default is not None:
            conditions.append(Agent.is_default == is_default)

        # Get total count
        count_stmt = select(func.count(Agent.id)).where(and_(*conditions))
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar()

        # Get agents
        stmt = (
            select(Agent)
            .options(
                selectinload(Agent.tools),
                selectinload(Agent.collections),
                selectinload(Agent.workflows),
                selectinload(Agent.team),
                selectinload(Agent.llm_provider),
            )
            .where(and_(*conditions))
            .order_by(Agent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        agents = result.scalars().all()

        # Enrich agents with collection data, workflow data, and tool details
        enriched_agents = await self.enrich_agents_with_collection_data(list(agents), project_id)
        enriched_agents = await self.enrich_agents_with_workflow_data(enriched_agents, project_id)
        enriched_agents = await self.enrich_agents_with_tool_details(enriched_agents, project_id)

        return enriched_agents, total_count

    async def update_agent(
        self, project_id: uuid.UUID, agent_id: uuid.UUID, agent_data: AgentUpdate
    ) -> Agent:
        """
        Update an agent.

        Args:
            project_id: Project ID
            agent_id: Agent ID
            agent_data: Agent update data

        Returns:
            Updated agent

        Raises:
            NotFoundError: If agent or team not found
            ValidationError: If team belongs to different project
        """
        # Get existing agent
        agent = await self.get_agent(project_id, agent_id)

        # Validate team if provided
        if agent_data.team_id is not None:
            await self._validate_team_belongs_to_project(agent_data.team_id, project_id)

        # Validate collections if provided
        if agent_data.collections is not None:
            await self._validate_collections_belong_to_project(agent_data.collections, project_id)

        # Validate workflows if provided
        if agent_data.workflows is not None:
            await self._validate_workflows_belong_to_project(agent_data.workflows, project_id)

        # Validate tools if provided
        if agent_data.tools is not None:
            tool_ids = [tool.tool_id for tool in agent_data.tools]
            await self._validate_tools_belong_to_project(tool_ids, project_id)

        # Update basic fields
        update_data = agent_data.model_dump(exclude_unset=True, exclude={"tools", "collections", "workflows"})
        for field, value in update_data.items():
            setattr(agent, field, value)

        # Update tools if provided
        if agent_data.tools is not None:
            # Delete existing tool associations
            stmt_delete = select(AgentToolAssociation).where(
                and_(
                    AgentToolAssociation.agent_id == agent.id,
                    AgentToolAssociation.deleted_at.is_(None),
                )
            )
            result = await self.db.execute(stmt_delete)
            existing_associations = result.scalars().all()
            for association in existing_associations:
                await self.db.delete(association)

            # Create new tool associations
            for tool_binding in agent_data.tools:
                association = AgentToolAssociation(
                    agent_id=agent.id,
                    tool_id=tool_binding.tool_id,
                    enabled=tool_binding.enabled,
                    permissions=tool_binding.permissions,
                    config=tool_binding.config,
                )
                self.db.add(association)

            await self.db.flush()

        # Update collections if provided
        if agent_data.collections is not None:
            # Remove existing collection associations
            for agent_collection in agent.collections:
                await self.db.delete(agent_collection)

            # Add new collection associations
            for collection_id_str in agent_data.collections:
                agent_collection = AgentCollection(
                    agent_id=agent.id,
                    collection_id=collection_id_str,
                )
                self.db.add(agent_collection)

        # Update workflows if provided
        if agent_data.workflows is not None:
            # Remove existing workflow associations
            for agent_workflow in agent.workflows:
                await self.db.delete(agent_workflow)

            # Add new workflow associations
            for workflow_id_str in agent_data.workflows:
                agent_workflow = AgentWorkflow(
                    agent_id=agent.id,
                    workflow_id=workflow_id_str,
                )
                self.db.add(agent_workflow)

        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def delete_agent(self, project_id: uuid.UUID, agent_id: uuid.UUID) -> None:
        """
        Soft delete an agent.

        Args:
            project_id: Project ID
            agent_id: Agent ID

        Raises:
            NotFoundError: If agent not found
        """
        agent = await self.get_agent(project_id, agent_id)
        agent.soft_delete()
        await self.db.commit()

    async def set_tool_enabled(
        self, project_id: uuid.UUID, agent_id: uuid.UUID, tool_id: uuid.UUID, enabled: bool
    ) -> None:
        """Enable or disable a specific tool binding for an agent."""
        # Verify agent belongs to project
        stmt_agent = select(Agent).where(
            and_(Agent.id == agent_id, Agent.project_id == project_id, Agent.deleted_at.is_(None))
        )
        res = await self.db.execute(stmt_agent)
        agent = res.scalar_one_or_none()
        if not agent:
            raise NotFoundError("Agent", agent_id)

        # Find association binding by agent and tool ID
        stmt_tool = select(AgentToolAssociation).where(
            and_(
                AgentToolAssociation.agent_id == agent_id,
                AgentToolAssociation.tool_id == tool_id,
                AgentToolAssociation.deleted_at.is_(None),
            )
        )
        res_tool = await self.db.execute(stmt_tool)
        binding = res_tool.scalar_one_or_none()
        if not binding:
            raise NotFoundError("AgentToolAssociation", details={"tool_id": str(tool_id)})

        binding.enabled = enabled
        await self.db.commit()

    async def set_collection_enabled(
        self, project_id: uuid.UUID, agent_id: uuid.UUID, collection_id: str, enabled: bool
    ) -> None:
        """Enable or disable a specific collection binding for an agent."""
        # Verify agent belongs to project
        stmt_agent = select(Agent).where(
            and_(Agent.id == agent_id, Agent.project_id == project_id, Agent.deleted_at.is_(None))
        )
        res = await self.db.execute(stmt_agent)
        agent = res.scalar_one_or_none()
        if not agent:
            raise NotFoundError("Agent", agent_id)

        # Find binding
        stmt_col = select(AgentCollection).where(
            and_(
                AgentCollection.agent_id == agent_id,
                AgentCollection.collection_id == collection_id,
                AgentCollection.deleted_at.is_(None),
            )
        )
        res_col = await self.db.execute(stmt_col)
        binding = res_col.scalar_one_or_none()
        if not binding:
            raise NotFoundError("AgentCollection", details={"collection_id": collection_id})

        binding.enabled = enabled
        await self.db.commit()

    async def set_workflow_enabled(
        self, project_id: uuid.UUID, agent_id: uuid.UUID, workflow_id: str, enabled: bool
    ) -> None:
        """Enable or disable a specific workflow binding for an agent."""
        # Verify agent belongs to project
        stmt_agent = select(Agent).where(
            and_(Agent.id == agent_id, Agent.project_id == project_id, Agent.deleted_at.is_(None))
        )
        res = await self.db.execute(stmt_agent)
        agent = res.scalar_one_or_none()
        if not agent:
            raise NotFoundError("Agent", agent_id)

        # Find binding
        stmt_wf = select(AgentWorkflow).where(
            and_(
                AgentWorkflow.agent_id == agent_id,
                AgentWorkflow.workflow_id == workflow_id,
            )
        )
        res_wf = await self.db.execute(stmt_wf)
        binding = res_wf.scalar_one_or_none()
        if not binding:
            raise NotFoundError("AgentWorkflow", details={"workflow_id": workflow_id})

        binding.enabled = enabled
        await self.db.commit()

    async def clear_session_memory(
        self, session_id: str, project_id: uuid.UUID, user_id: Optional[str] = None
    ) -> None:
        """Clear all memory and session history for a specific session.
        
        This deletes records from agno memory and session tables in the 'ai' schema.
        If user_id is provided, it also clears personal memories for that user from agno_memories.
        """
        try:
            # Delete from agno_memories (user/agent memories)
            # The user noted that agno_memories uses user_id, not session_id
            if user_id:
                await self.db.execute(
                    text("DELETE FROM ai.agno_memories WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
            
            # Delete from agno_sessions (session history)
            # We use try/except as the table might not exist yet
            try:
                await self.db.execute(
                    text("DELETE FROM ai.agno_sessions WHERE session_id = :session_id"),
                    {"session_id": session_id}
                )
            except Exception:
                # Table might not exist yet, which is fine
                pass
            
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    async def _validate_team_belongs_to_project(
        self, team_id: uuid.UUID, project_id: uuid.UUID
    ) -> None:
        """
        Validate that a team belongs to the specified project.

        Args:
            team_id: Team ID
            project_id: Project ID

        Raises:
            NotFoundError: If team not found
            ValidationError: If team belongs to different project
        """
        stmt = select(Team).where(
            and_(
                Team.id == team_id,
                Team.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        team = result.scalar_one_or_none()

        if not team:
            raise NotFoundError("Team", team_id)

        if team.project_id != project_id:
            raise ValidationError(
                "Team belongs to a different project",
                "team_id",
                {"team_project_id": str(team.project_id), "expected_project_id": str(project_id)},
            )

    async def _validate_collections_belong_to_project(
        self, collection_ids: List[str], project_id: uuid.UUID
    ) -> None:
        """
        Validate that all collections exist in the RAG service for the project.

        Args:
            collection_ids: List of collection ID strings
            project_id: Project ID

        Raises:
            NotFoundError: If any collection not found
            ValidationError: If validation fails
        """
        if not collection_ids:
            return

        # Validate collections exist in RAG service (trust project_id; no local project validation)
        await rag_service_client.validate_collections_exist(
            collection_ids,
            str(project_id),
        )

    async def _validate_workflows_belong_to_project(
        self, workflow_ids: List[str], project_id: uuid.UUID
    ) -> None:
        """
        Validate that all workflows exist in the Workflow service for the project.

        Args:
            workflow_ids: List of workflow ID strings
            project_id: Project ID

        Raises:
            NotFoundError: If any workflow not found
            ValidationError: If validation fails
        """
        if not workflow_ids:
            return

        # Validate workflows exist in Workflow service
        await workflow_service_client.validate_workflows_exist(
            workflow_ids,
            str(project_id),
        )

    async def _validate_tools_belong_to_project(
        self, tool_ids: List[uuid.UUID], project_id: uuid.UUID
    ) -> None:
        """
        Validate that all tools exist in the ai_tools table and belong to the project.

        Args:
            tool_ids: List of tool IDs
            project_id: Project ID

        Raises:
            NotFoundError: If any tool not found
            ValidationError: If any tool belongs to different project
        """
        if not tool_ids:
            return

        # Query tools from database
        stmt = select(Tool).where(
            and_(
                Tool.id.in_(tool_ids),
                Tool.deleted_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        tools = result.scalars().all()

        # Check if all tools were found
        found_tool_ids = {tool.id for tool in tools}
        missing_tool_ids = set(tool_ids) - found_tool_ids
        if missing_tool_ids:
            raise NotFoundError(
                "Tool",
                details={"missing_tool_ids": [str(tid) for tid in missing_tool_ids]},
            )

        # Check if all tools belong to the project
        wrong_project_tools = [tool for tool in tools if tool.project_id != project_id]
        if wrong_project_tools:
            raise ValidationError(
                "Some tools belong to a different project",
                "tool_ids",
                {
                    "wrong_project_tool_ids": [str(tool.id) for tool in wrong_project_tools],
                    "expected_project_id": str(project_id),
                },
            )

    async def enrich_agents_with_collection_data(
        self, agents: List[Agent], project_id: uuid.UUID
    ) -> List[Agent]:
        """
        Enrich agents with collection data from the RAG service.

        Args:
            agents: List of agents to enrich
            project_id: Project ID for RAG service authentication

        Returns:
            List of agents with collection data attached
        """
        if not agents:
            return agents

        # Skip local project existence check; rely on upstream services and use project_id directly

        # Collect all unique collection IDs from all agents
        all_collection_ids = set()
        for agent in agents:
            for ac in (agent.collections or []):
                all_collection_ids.add(ac.collection_id)

        if not all_collection_ids:
            # No collections to fetch
            for agent in agents:
                agent._collection_data = []
            return agents

        # Fetch collection data from RAG service
        try:
            batch_response = await rag_service_client.get_collections_batch(
                list(all_collection_ids),
                str(project_id),
            )

            # Create a mapping of collection_id -> collection_data
            collection_data_map = {
                str(collection.id): collection
                for collection in batch_response.collections
            }

            # Attach collection data (with enabled from binding) to each agent
            for agent in agents:
                agent_collection_data = []
                for ac in (agent.collections or []):
                    cid = str(ac.collection_id)
                    if cid in collection_data_map:
                        col = collection_data_map[cid]
                        try:
                            col_with_enabled = col.model_copy(update={"enabled": bool(getattr(ac, "enabled", True))})
                        except Exception:
                            col_with_enabled = col
                        agent_collection_data.append(col_with_enabled)
                agent._collection_data = agent_collection_data

        except Exception:
            # If RAG service fails, return agents without collection data
            for agent in agents:
                agent._collection_data = []

        return agents

    async def enrich_agents_with_workflow_data(
        self, agents: List[Agent], project_id: uuid.UUID
    ) -> List[Agent]:
        """
        Enrich agents with workflow data from the Workflow service.

        Args:
            agents: List of agents to enrich
            project_id: Project ID for Workflow service authentication

        Returns:
            List of agents with workflow data attached
        """
        if not agents:
            return agents

        # Collect all unique workflow IDs from all agents
        all_workflow_ids = set()
        for agent in agents:
            for aw in (agent.workflows or []):
                all_workflow_ids.add(aw.workflow_id)

        if not all_workflow_ids:
            # No workflows to fetch
            for agent in agents:
                agent._workflow_data = []
            return agents

        # Fetch workflow data from Workflow service
        try:
            workflows = await workflow_service_client.get_workflows_batch(
                list(all_workflow_ids),
                str(project_id),
            )

            # Create a mapping of workflow_id -> workflow_data
            workflow_data_map = {
                str(workflow.id): workflow
                for workflow in workflows
            }

            # Attach workflow data (with enabled from binding) to each agent
            for agent in agents:
                agent_workflow_data = []
                for aw in (agent.workflows or []):
                    wid = str(aw.workflow_id)
                    if wid in workflow_data_map:
                        wf = workflow_data_map[wid]
                        try:
                            wf_with_enabled = wf.model_copy(update={"enabled": bool(getattr(aw, "enabled", True))})
                        except Exception:
                            wf_with_enabled = wf
                        agent_workflow_data.append(wf_with_enabled)
                agent._workflow_data = agent_workflow_data

        except Exception:
            # If Workflow service fails, return agents without workflow data
            for agent in agents:
                agent._workflow_data = []

        return agents

    async def enrich_agents_with_tool_details(
        self, agents: List[Agent], project_id: uuid.UUID
    ) -> List[Agent]:
        """
        Enrich agents with tool details from local database (ai_tools table).

        Flow:
        - Load agent tool bindings (already present via selectinload in callers)
        - Build AgentToolDetail objects from Tool entities
        - Attach enabled state and other association fields from AgentToolAssociation
        - Set agent._tools_data with enriched tool list
        """
        if not agents:
            return agents

        # Build association map: (agent_id, tool_id) -> (enabled, permissions, config)
        assoc_stmt = (
            select(
                AgentToolAssociation.agent_id,
                AgentToolAssociation.tool_id,
                AgentToolAssociation.enabled,
                AgentToolAssociation.permissions,
                AgentToolAssociation.config,
            )
            .where(
                and_(
                    AgentToolAssociation.agent_id.in_([a.id for a in agents]),
                    AgentToolAssociation.deleted_at.is_(None),
                )
            )
        )
        assoc_res = await self.db.execute(assoc_stmt)
        assoc_map: Dict[Tuple[uuid.UUID, uuid.UUID], Tuple[bool, Optional[List[str]], Optional[dict]]] = {
            (row[0], row[1]): (bool(row[2]), row[3], row[4]) for row in assoc_res.all()
        }

        # Import AgentToolDetail here to avoid circular import
        from app.schemas.tool import AgentToolDetail

        # Attach per-agent tool details preserving original binding order
        for agent in agents:
            tool_details = []
            for tool_entity in (agent.tools or []):
                if not tool_entity:
                    continue

                # Get association data
                assoc_data = assoc_map.get((agent.id, tool_entity.id), (True, None, None))
                enabled, permissions, tool_config = assoc_data

                # Build AgentToolDetail from Tool entity with association fields
                try:
                    # First convert Tool to dict
                    tool_dict = {
                        "id": tool_entity.id,
                        "project_id": tool_entity.project_id,
                        "name": tool_entity.name,
                        "description": tool_entity.description,
                        "tool_type": tool_entity.tool_type,
                        "transport_type": tool_entity.transport_type,
                        "endpoint": tool_entity.endpoint,
                        "config": tool_entity.config,
                        "created_at": tool_entity.created_at,
                        "updated_at": tool_entity.updated_at,
                        "deleted_at": tool_entity.deleted_at,
                        "enabled": enabled,
                        "permissions": permissions,
                        "tool_config": tool_config,
                    }

                    tool_detail = AgentToolDetail(**tool_dict)
                    tool_details.append(tool_detail)
                except Exception:
                    # Skip tools that fail validation
                    continue

            agent._tools_data = tool_details

        return agents
