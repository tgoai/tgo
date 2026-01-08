import { BaseApiService } from './base/BaseApiService';
import type { Agent, TeamAdvancedConfig } from '@/types';

// Team response from API
export interface TeamResponse {
  id: string;
  name: string;
  model: string;
  instruction: string | null;
  expected_output: string | null;
  session_id: string | null;
  is_default: boolean;
  config?: TeamAdvancedConfig | null;
  created_at?: string;
  updated_at?: string;
}

// Team with details (includes agents)
export interface TeamWithDetailsResponse extends TeamResponse {
  agents?: Agent[];
}

// Team update request
export interface TeamUpdateRequest {
  name?: string | null;
  ai_provider_id?: string | null;
  model?: string | null;
  instruction?: string | null;
  expected_output?: string | null;
  session_id?: string | null;
  is_default?: boolean | null;
  config?: TeamAdvancedConfig | null;
}

class AITeamsApiService extends BaseApiService {
  protected readonly apiVersion = 'v1';
  protected readonly endpoints = {
    default: '/v1/ai/teams/default',
    teams: '/v1/ai/teams',
    team: (teamId: string) => `/v1/ai/teams/${teamId}`,
  } as const;

  /**
   * Get the default team for the authenticated project
   * @param includeAgents - Whether to include associated agents
   */
  async getDefaultTeam(includeAgents: boolean = false): Promise<TeamWithDetailsResponse> {
    const params = includeAgents ? '?include_agents=true' : '?include_agents=false';
    return this.get<TeamWithDetailsResponse>(`${this.endpoints.default}${params}`);
  }

  /**
   * Get a team by ID
   * @param teamId - The team UUID
   * @param includeAgents - Whether to include associated agents
   */
  async getTeam(teamId: string, includeAgents: boolean = false): Promise<TeamWithDetailsResponse> {
    const params = includeAgents ? '?include_agents=true' : '?include_agents=false';
    return this.get<TeamWithDetailsResponse>(`${this.endpoints.team(teamId)}${params}`);
  }

  /**
   * Update a team
   * @param teamId - The team UUID
   * @param data - The update data
   */
  async updateTeam(teamId: string, data: TeamUpdateRequest): Promise<TeamResponse> {
    return this.patch<TeamResponse>(this.endpoints.team(teamId), data);
  }
}

export const aiTeamsApiService = new AITeamsApiService();
export default aiTeamsApiService;

