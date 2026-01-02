/**
 * Workflow API Service
 * Handles all communication with the backend for AI Agent Workflows
 * Strictly follows the OpenAPI specification in docs/api.json
 */

import apiClient from './api';
import type { 
  Workflow, 
  WorkflowListResponse,
  WorkflowCreateRequest,
  WorkflowUpdateRequest,
  WorkflowExecution,
  WorkflowQueryParams,
  WorkflowStreamEvent
} from '@/types/workflow';

export class WorkflowApiService {
  private static BASE_PATH = '/v1/ai/workflows';

  /**
   * List all workflows with pagination and filtering
   */
  static async listWorkflows(params: WorkflowQueryParams = {}): Promise<WorkflowListResponse> {
    const query = new URLSearchParams();
    if (params.status) query.append('status', params.status);
    if (params.search) query.append('search', params.search);
    if (params.limit) query.append('limit', params.limit.toString());
    if (params.offset) query.append('offset', params.offset.toString());
    if (params.tags && params.tags.length > 0) {
      params.tags.forEach(tag => query.append('tags', tag));
    }

    const queryString = query.toString();
    const endpoint = queryString ? `${this.BASE_PATH}?${queryString}` : this.BASE_PATH;
    
    return apiClient.get<WorkflowListResponse>(endpoint);
  }

  /**
   * Get a single workflow by ID
   */
  static async getWorkflow(id: string): Promise<Workflow> {
    return apiClient.get<Workflow>(`${this.BASE_PATH}/${id}`);
  }

  /**
   * Create a new workflow
   */
  static async createWorkflow(request: WorkflowCreateRequest): Promise<Workflow> {
    return apiClient.post<Workflow>(this.BASE_PATH, request);
  }

  /**
   * Update an existing workflow
   */
  static async updateWorkflow(id: string, request: WorkflowUpdateRequest): Promise<Workflow> {
    return apiClient.put<Workflow>(`${this.BASE_PATH}/${id}`, request);
  }

  /**
   * Delete a workflow
   */
  static async deleteWorkflow(id: string): Promise<void> {
    return apiClient.delete(`${this.BASE_PATH}/${id}`);
  }

  /**
   * Duplicate an existing workflow
   */
  static async duplicateWorkflow(id: string, name?: string): Promise<Workflow> {
    return apiClient.post<Workflow>(`${this.BASE_PATH}/${id}/duplicate`, { name });
  }

  /**
   * Validate a workflow's structure and data
   */
  static async validateWorkflow(id: string): Promise<{ valid: boolean; errors: string[] }> {
    return apiClient.post<{ valid: boolean; errors: string[] }>(`${this.BASE_PATH}/${id}/validate`);
  }

  /**
   * Publish a workflow to make it active
   */
  static async publishWorkflow(id: string): Promise<Workflow> {
    return apiClient.post<Workflow>(`${this.BASE_PATH}/${id}/publish`);
  }

  /**
   * Execute a workflow
   */
  static async executeWorkflow(id: string, input?: Record<string, any>): Promise<WorkflowExecution> {
    return apiClient.post<WorkflowExecution>(`${this.BASE_PATH}/${id}/execute`, { inputs: input });
  }

  /**
   * Get an execution's status and results
   */
  static async getExecution(executionId: string): Promise<WorkflowExecution> {
    return apiClient.get<WorkflowExecution>(`${this.BASE_PATH}/executions/${executionId}`);
  }

  /**
   * Cancel a running execution
   */
  static async cancelExecution(executionId: string): Promise<void> {
    await apiClient.post(`${this.BASE_PATH}/executions/${executionId}/cancel`);
  }

  /**
   * List executions for a specific workflow
   */
  static async listExecutions(workflowId: string): Promise<WorkflowExecution[]> {
    return apiClient.get<WorkflowExecution[]>(`${this.BASE_PATH}/${workflowId}/executions`);
  }

  /**
   * Execute a workflow using streaming SSE events
   */
  static async executeWorkflowStream(
    id: string, 
    input: Record<string, any>, 
    onEvent: (event: WorkflowStreamEvent) => void,
    signal?: AbortSignal
  ): Promise<void> {
    return apiClient.stream(
      `${this.BASE_PATH}/${id}/execute/stream`,
      { inputs: input }, // Updated to match WorkflowExecuteRequest schema
      {
        onMessage: (event, data) => {
          onEvent({ event: event as any, ...data });
        },
        signal
      }
    );
  }

  /**
   * Get available variables for a node in a workflow
   */
  static async getAvailableVariables(workflowId: string): Promise<any> {
    return apiClient.get(`${this.BASE_PATH}/${workflowId}/variables`);
  }
}
