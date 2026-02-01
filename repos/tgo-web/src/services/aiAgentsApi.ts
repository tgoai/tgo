/**
 * AI Agents API Service
 * Handles AI Agents API endpoints following the BaseApiService pattern
 */

import BaseApiService from './base/BaseApiService';
import type {
  AgentListResponse,
  AgentWithDetailsResponse,
  AgentCreateRequest,
  AgentUpdateRequest,
  AgentQueryParams,
  AgentToolCreateRequest,
  AgentToolResponse,
  ToolSummary
} from '@/types';

/**
 * AI Agents API Service Class
 */
export class AIAgentsApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    AGENTS: `/${this.apiVersion}/ai/agents`,
    AGENT_BY_ID: (id: string) => `/${this.apiVersion}/ai/agents/${id}`,
  } as const;

  /**
   * Get paginated list of AI agents
   */
  static async getAgents(params?: AgentQueryParams): Promise<AgentListResponse> {
    const service = new AIAgentsApiService();
    return service.get<AgentListResponse>(service.endpoints.AGENTS, params);
  }

  /**
   * Get a specific agent by ID (returns detailed response with tools and collections)
   */
  static async getAgent(id: string): Promise<AgentWithDetailsResponse> {
    const service = new AIAgentsApiService();
    const endpoint = service.endpoints.AGENT_BY_ID(id);
    return service.get<AgentWithDetailsResponse>(endpoint);
  }

  /**
   * Create a new agent (returns detailed response with tools and collections)
   */
  static async createAgent(agentData: AgentCreateRequest): Promise<AgentWithDetailsResponse> {
    const service = new AIAgentsApiService();
    return service.post<AgentWithDetailsResponse>(service.endpoints.AGENTS, agentData);
  }

  /**
   * Update an existing agent (returns detailed response with tools and collections)
   */
  static async updateAgent(id: string, agentData: AgentUpdateRequest): Promise<AgentWithDetailsResponse> {
    const service = new AIAgentsApiService();
    const endpoint = service.endpoints.AGENT_BY_ID(id);
    return service.patch<AgentWithDetailsResponse>(endpoint, agentData);
  }

  /**
   * Delete an agent
   */
  static async deleteAgent(id: string): Promise<void> {
    const service = new AIAgentsApiService();
    const endpoint = service.endpoints.AGENT_BY_ID(id);
    return service.delete<void>(endpoint);
  }

  /**
   * Search agents with specific filters
   * Note: The API doesn't have a search parameter, so this filters by other criteria
   */
  static async searchAgents(
    _query: string, // Prefix with underscore to indicate intentionally unused
    filters?: {
      model?: string;
      is_default?: boolean;
      limit?: number;
    }
  ): Promise<AgentListResponse> {
    const service = new AIAgentsApiService();
    const params: AgentQueryParams = {
      limit: filters?.limit || 20,
      model: filters?.model,
      is_default: filters?.is_default,
    };

    // Note: The API doesn't have a search parameter, so we'll filter client-side
    // or implement server-side search if needed
    return service.get<AgentListResponse>(service.endpoints.AGENTS, params);
  }

  /**
   * Get agents by model
   */
  static async getAgentsByModel(
    model: string,
    params?: Omit<AgentQueryParams, 'model'>
  ): Promise<AgentListResponse> {
    const service = new AIAgentsApiService();
    return service.get<AgentListResponse>(service.endpoints.AGENTS, { ...params, model });
  }

  /**
   * Get default agents
   */
  static async getDefaultAgents(
    params?: Omit<AgentQueryParams, 'is_default'>
  ): Promise<AgentListResponse> {
    const service = new AIAgentsApiService();
    return service.get<AgentListResponse>(service.endpoints.AGENTS, { ...params, is_default: true });
  }

  /**
   * Get agents with pagination
   */
  static async getAgentsPage(
    page: number,
    pageSize: number = 20,
    filters?: Omit<AgentQueryParams, 'limit' | 'offset'>
  ): Promise<AgentListResponse> {
    const service = new AIAgentsApiService();
    const offset = (page - 1) * pageSize;
    return service.get<AgentListResponse>(service.endpoints.AGENTS, {
      ...filters,
      limit: pageSize,
      offset,
    });
  }
}

// Removed legacy AgentTransformUtils to avoid duplication.

/**
 * Agent transformation utilities
 */
export class AIAgentsTransformUtils {
  /**
   * Transform Tool tool IDs to AgentToolCreateRequest array
   */
  static transformToolsToAgentTools(
    toolIds: string[],
    toolConfigs: Record<string, Record<string, any>>,
    _availableTools?: ToolSummary[], // Prefixed with _ to indicate intentionally unused
  ): AgentToolCreateRequest[] {
    return toolIds.map(toolId => {
      const config = toolConfigs[toolId] || null;

      return {
        tool_id: toolId, // Pass the tool UUID directly
        enabled: true, // Tools are always enabled when attached to an agent
        permissions: null, // No specific permissions for now
        config: config,
      };
    });
  }

  /**
   * Transform CreateAgentFormData to AgentCreateRequest for API
   */
  static transformFormDataToCreateRequest(
    formData: import('@/types').CreateAgentFormData,
    availableTools?: ToolSummary[],
  ): AgentCreateRequest {
    const isComputerUseAgent = formData.agentCategory === 'computer_use';

    // Transform Tool tools to the API format (always pass array, never null)
    // For computer_use agents, don't include tools
    const tools = !isComputerUseAgent && formData.tools.length > 0 ?
      AIAgentsTransformUtils.transformToolsToAgentTools(
        formData.tools,
        formData.toolConfigs,
        availableTools,
      ) : [];

    // Transform knowledge bases to collections (UUID strings, always pass array, never null)
    // For computer_use agents, don't include knowledge bases
    const collections = !isComputerUseAgent && formData.knowledgeBases && formData.knowledgeBases.length > 0 ?
      formData.knowledgeBases : [];

    // For computer_use agents, don't include workflows
    const workflowIds = !isComputerUseAgent ? (formData.workflows || []) : [];

    // Split UI model value (providerId:modelName) into separate fields
    const rawModel = formData.llmModel || '';
    const hasProvider = rawModel.includes(':');
    const providerId = hasProvider ? rawModel.split(':')[0] : null;
    const modelName = hasProvider ? rawModel.split(':').slice(1).join(':') : (isComputerUseAgent ? 'computer-use' : rawModel);

    // Build config object
    const configObj: Record<string, any> = {
      profession: formData.profession,
      markdown: isComputerUseAgent ? true : formData.markdown,
      add_datetime_to_context: isComputerUseAgent ? true : formData.add_datetime_to_context,
      tool_call_limit: isComputerUseAgent ? 20 : formData.tool_call_limit,
      num_history_runs: isComputerUseAgent ? 10 : formData.num_history_runs,
    };

    // For computer_use agents, include bound_device_id in config
    if (isComputerUseAgent && formData.boundDeviceId) {
      configObj.bound_device_id = formData.boundDeviceId;
    }

    return {
      name: formData.name,
      instruction: formData.description || null,
      ai_provider_id: providerId,
      model: modelName, // pure model name (no provider prefix)
      is_default: false, // Default to false
      agent_category: formData.agentCategory || 'normal', // Agent category
      config: configObj,
      team_id: null, // Optional - can be set later if needed
      tools: tools,
      collections: collections,
      workflows: workflowIds,
      // Include bound_device_id at top level for API compatibility
      ...(isComputerUseAgent && formData.boundDeviceId
        ? { bound_device_id: formData.boundDeviceId }
        : {}),
    };
  }

  /**
   * Transform API AgentWithDetailsResponse to UI Agent format
   */
  static transformApiAgentToAgent(apiAgent: import('@/types').AgentWithDetailsResponse): import('@/types').Agent {
    // Extract tool IDs and configs from the tools array (for backward compatibility)
    const toolIds = apiAgent.tools?.map(tool => tool.id) || [];
    const toolConfigs = AIAgentsTransformUtils.extractToolConfigs(apiAgent.tools);

    // Extract collection IDs from the collections array (for backward compatibility)
    const knowledgeBases = apiAgent.collections?.map(collection => collection.id) || [];

    // Preserve full collection objects for display purposes
    const collections = apiAgent.collections || [];

    // Preserve full tool objects for display purposes
    const tools = apiAgent.tools || [];

    return {
      id: apiAgent.id,
      name: apiAgent.name,
      description: apiAgent.instruction || '',
      avatar: '/api/placeholder/40/40', // Default avatar
      status: 'active' as const,
      type: 'expert' as const,
      role: apiAgent.config?.profession || '专家',
      llmModel: (apiAgent as any).ai_provider_id && apiAgent.model ? `${(apiAgent as any).ai_provider_id}:${apiAgent.model}` : (apiAgent.model || ''),
      endpoint: undefined,
      capabilities: apiAgent.config?.capabilities || [],
      lastActive: new Date(apiAgent.updated_at).toISOString().split('T')[0],
      conversationCount: 0, // Not available in API
      successRate: 0.95, // Default success rate
      responseTime: '1.2s', // Default response time
      tags: [apiAgent.model], // Use model as tag
      agent_category: apiAgent.agent_category || 'normal', // Agent category
      tools: toolIds,
      toolConfigs: toolConfigs,
      knowledgeBases: knowledgeBases,
      collections: collections,
      agentTools: tools,
      workflows: (apiAgent as any).workflows || [],
      config: {
        profession: apiAgent.config?.profession,
        markdown: apiAgent.config?.markdown,
        add_datetime_to_context: apiAgent.config?.add_datetime_to_context,
        tool_call_limit: apiAgent.config?.tool_call_limit,
        num_history_runs: apiAgent.config?.num_history_runs,
        bound_device_id: apiAgent.config?.bound_device_id, // Preserve bound device ID
      },
    };
  }

  /**
   * Extract tool configurations from API tools
   */
  static extractToolConfigs(tools?: AgentToolResponse[]): Record<string, Record<string, any>> {
    if (!tools) return {};

    const configs: Record<string, Record<string, any>> = {};
    tools.forEach(tool => {
      if (tool.id && tool.config) {
        configs[tool.id] = tool.config;
      }
    });

    return configs;
  }

  /**
   * Transform Agent to AgentUpdateRequest for updates
   */
  static transformAgentToUpdateRequest(
    agent: import('@/types').Agent,
    availableTools?: ToolSummary[]
  ): AgentUpdateRequest {
    // Build available tools from agent.tools if not provided
    let resolvedAvailableTools = availableTools;
    if ((!resolvedAvailableTools || resolvedAvailableTools.length === 0) && (agent as any).tools) {
      const toolDetails: any[] = (agent as any).tools || [];
      resolvedAvailableTools = toolDetails.map((t) => {
        // Derive short_no and simple name from legacy AgentToolResponse.tool_name if present
        let derivedShortNo: string | null = t?.tool_server?.short_no || null;
        let derivedName: string | null = t?.name || t?.title || null;
        if (!derivedShortNo || !derivedName) {
          const tn: string | undefined = t?.tool_name;
          if (typeof tn === 'string') {
            const parts = tn.split(':');
            if (parts.length >= 2) {
              const provider = parts[0];
              const name = parts.slice(1).join(':');
              derivedShortNo = derivedShortNo || provider || null;
              derivedName = derivedName || name || null;
            }
          }
        }

        return {
          id: t.id,
          name: derivedName || 'tool',
          title: t.title || t.name || derivedName || 'tool',
          description: t.description || null,
          version: t.version || '1.0.0',
          category: t.category || null,
          tags: Array.isArray(t.tags) ? t.tags : [],
          status: (t.status as any) || 'ACTIVE',
          tool_source_type: (t.tool_source_type as any) || 'Tool_SERVER',
          execution_count: null,
          created_at: t.created_at || new Date().toISOString(),
          tool_server_id: t.tool_server_id || (t.tool_server?.id ?? null),
          input_schema: t.input_schema || {},
          output_schema: t.output_schema || null,
          short_no: derivedShortNo || null,
          is_installed: undefined,
        } as ToolSummary;
      }) as ToolSummary[];
    }

    // Transform Tool tools to the API format (always pass array, never null)
    const tools = agent.tools && agent.tools.length > 0 ?
      AIAgentsTransformUtils.transformToolsToAgentTools(
        agent.tools,
        agent.toolConfigs || {},
        resolvedAvailableTools,
      ) : [];

    // Transform knowledge bases to collections (UUID strings, always pass array, never null)
    const collections = agent.knowledgeBases && agent.knowledgeBases.length > 0 ?
      agent.knowledgeBases : [];

    // Split UI model value (providerId:modelName) if present
    const rawModel = agent.llmModel || '';
    const hasProvider = rawModel.includes(':');
    const providerId = hasProvider ? rawModel.split(':')[0] : null;
    const modelName = rawModel ? (hasProvider ? rawModel.split(':').slice(1).join(':') : rawModel) : (agent.agent_category === 'computer_use' ? 'computer-use' : null);

    // Build config object, including bound_devices for computer_use agents
    const configObj: Record<string, any> = {
      profession: agent.role,
      capabilities: agent.capabilities,
      markdown: agent.agent_category === 'computer_use' ? true : agent.config?.markdown,
      add_datetime_to_context: agent.agent_category === 'computer_use' ? true : agent.config?.add_datetime_to_context,
      tool_call_limit: agent.agent_category === 'computer_use' ? 20 : agent.config?.tool_call_limit,
      num_history_runs: agent.agent_category === 'computer_use' ? 10 : agent.config?.num_history_runs,
    };

    // For computer_use agents, include bound_device_id in config
    if (agent.agent_category === 'computer_use' && agent.config?.bound_device_id) {
      configObj.bound_device_id = agent.config.bound_device_id;
    }

    return {
      name: agent.name,
      instruction: agent.description,
      ...(providerId ? { ai_provider_id: providerId } : {}),
      ...(modelName ? { model: modelName } : {}),
      ...(agent.agent_category ? { agent_category: agent.agent_category } : {}),
      config: configObj,
      tools: tools,
      collections: collections,
      workflows: agent.workflows || [],
      // Include bound_device_id at top level for API compatibility
      ...(agent.agent_category === 'computer_use' && agent.config?.bound_device_id
        ? { bound_device_id: agent.config.bound_device_id }
        : {}),
    } as AgentUpdateRequest;
  }

  /**
   * Ensure model ID has proper format (provider:model_name)
   */
  static ensureModelFormat(modelId: string): string {
    if (modelId.includes(':') && modelId.split(':').length === 2) {
      return modelId;
    }

    // If no provider prefix, add a default one based on common patterns
    if (modelId.startsWith('gpt-')) {
      return `openai:${modelId}`;
    } else if (modelId.startsWith('claude-')) {
      return `anthropic:${modelId}`;
    } else if (modelId.startsWith('gemini-')) {
      return `google:${modelId}`;
    } else {
      // Default to openai for unknown models
      return `openai:${modelId}`;
    }
  }
}

export default AIAgentsApiService;
