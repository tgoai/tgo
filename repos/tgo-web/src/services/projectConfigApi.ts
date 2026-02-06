import BaseApiService from './base/BaseApiService';

export interface ProjectAIConfigResponse {
  id: string;
  project_id: string;
  created_at: string;
  updated_at: string;
  deleted_at?: string | null;
  default_chat_provider_id: string | null;
  default_chat_model: string | null;
  default_embedding_provider_id: string | null;
  default_embedding_model: string | null;
  device_control_provider_id: string | null;
  device_control_model: string | null;
}

export interface ProjectAIConfigUpdate {
  default_chat_provider_id?: string | null;
  default_chat_model?: string | null;
  default_embedding_provider_id?: string | null;
  default_embedding_model?: string | null;
  device_control_provider_id?: string | null;
  device_control_model?: string | null;
}

export default class ProjectConfigApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    AI_CONFIG: (projectId: string) => `/${this.apiVersion}/projects/${projectId}/ai-config`,
  } as const;

  private aiConfigEndpoint(projectId: string) {
    return this.endpoints.AI_CONFIG(projectId);
  }

  async getAIConfig(projectId: string): Promise<ProjectAIConfigResponse> {
    return this.get<ProjectAIConfigResponse>(this.aiConfigEndpoint(projectId));
  }

  async upsertAIConfig(projectId: string, payload: ProjectAIConfigUpdate): Promise<ProjectAIConfigResponse> {
    return this.put<ProjectAIConfigResponse>(this.aiConfigEndpoint(projectId), payload);
  }
}

