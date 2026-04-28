import type { Platform } from '@/types';
import type { PlatformResponse, PlatformUpdateRequest } from '@/services/platformsApi';

const agentId = '123e4567-e89b-12d3-a456-426614174000';

export const platformUpdateUsesSingleAgentId: PlatformUpdateRequest = {
  agent_id: agentId,
};

export const readPlatformAgentId = (platform: Platform): string | null | undefined => platform.agent_id;

export const readPlatformResponseAgentId = (
  platform: PlatformResponse,
): string | null | undefined => platform.agent_id;

export const platformUpdateRejectsLegacyAgentIds: PlatformUpdateRequest = {
  // @ts-expect-error Platform updates must not send legacy multi-agent arrays.
  agent_ids: [agentId],
};
