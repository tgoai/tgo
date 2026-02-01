/**
 * Remote Agent Selector Component
 * Allows users to select remote agents to add to a team
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Monitor, Wifi, WifiOff, RefreshCw, Settings } from 'lucide-react';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import {
  listRemoteAgents,
  type RemoteAgentInfo,
  type RemoteAgentsListResponse,
} from '@/services/remoteAgentsApi';
import type { RemoteAgentTeamConfig } from '@/types/remoteAgent';

interface RemoteAgentSelectorProps {
  selectedAgents: RemoteAgentTeamConfig[];
  onChange: (agents: RemoteAgentTeamConfig[]) => void;
  onConfigureAgent?: (agent: RemoteAgentInfo) => void;
}

export function RemoteAgentSelector({
  selectedAgents,
  onChange,
  onConfigureAgent,
}: RemoteAgentSelectorProps) {
  const { t } = useTranslation();
  const [agents, setAgents] = useState<RemoteAgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = async () => {
    setLoading(true);
    setError(null);
    try {
      const response: RemoteAgentsListResponse = await listRemoteAgents();
      setAgents(response.items);
    } catch (err) {
      setError(t('remoteAgents.fetchError', 'Failed to fetch remote agents'));
      console.error('Failed to fetch remote agents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAgents();
  }, []);

  const handleToggleAgent = (agent: RemoteAgentInfo, checked: boolean) => {
    if (checked) {
      // Add agent with default config
      const config: RemoteAgentTeamConfig = {
        agent_id: agent.agent_id,
        base_url: agent.base_url,
        display_name: agent.name,
        description: agent.description,
      };
      onChange([...selectedAgents, config]);
    } else {
      // Remove agent
      onChange(selectedAgents.filter((a) => a.agent_id !== agent.agent_id));
    }
  };

  const isSelected = (agentId: string) => {
    return selectedAgents.some((a) => a.agent_id === agentId);
  };

  const getAgentIcon = (agent: RemoteAgentInfo) => {
    if (agent.type === 'computer_use') {
      return <Monitor className="w-5 h-5" />;
    }
    return <Settings className="w-5 h-5" />;
  };

  const getStatusBadge = (status: string) => {
    if (status === 'available') {
      return (
        <Badge className="bg-green-100 text-green-800 border-none">
          <Wifi className="w-3 h-3 mr-1" />
          {t('remoteAgents.available', 'Available')}
        </Badge>
      );
    }
    return (
      <Badge className="bg-gray-100 text-gray-600 border-none">
        <WifiOff className="w-3 h-3 mr-1" />
        {t('remoteAgents.unavailable', 'Unavailable')}
      </Badge>
    );
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">
            {t('remoteAgents.title', 'Remote Agents')}
          </h3>
        </div>
        {[1, 2].map((i) => (
          <div key={i} className="p-4 border rounded-lg bg-white shadow-sm">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-lg bg-gray-100 animate-pulse" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-32 bg-gray-100 animate-pulse rounded" />
                <div className="h-3 w-64 bg-gray-100 animate-pulse rounded" />
              </div>
              <div className="w-16 h-6 bg-gray-100 animate-pulse rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">
            {t('remoteAgents.title', 'Remote Agents')}
          </h3>
          <Button variant="secondary" onClick={fetchAgents}>
            <RefreshCw className="w-4 h-4 mr-1" />
            {t('common.retry', 'Retry')}
          </Button>
        </div>
        <div className="p-4 text-center text-gray-500 border rounded-lg">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-medium">
            {t('remoteAgents.title', 'Remote Agents')}
          </h3>
          <p className="text-sm text-gray-500">
            {t(
              'remoteAgents.description',
              'Select remote agents to add to your team, such as device control agents'
            )}
          </p>
        </div>
        <Button variant="secondary" onClick={fetchAgents}>
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {agents.length === 0 ? (
        <div className="p-8 text-center text-gray-500 border rounded-lg">
          {t('remoteAgents.noAgents', 'No remote agents available')}
        </div>
      ) : (
        <div className="space-y-3">
          {agents.map((agent) => (
            <div
              key={agent.agent_id}
              className={`p-4 border rounded-lg bg-white shadow-sm transition-colors ${
                isSelected(agent.agent_id)
                  ? 'border-blue-500 ring-1 ring-blue-500'
                  : 'hover:border-gray-300'
              } ${agent.status === 'unavailable' ? 'opacity-60' : ''}`}
              onClick={() => agent.status === 'available' && handleToggleAgent(agent, !isSelected(agent.agent_id))}
            >
              <div className="flex items-start gap-4">
                <input
                  type="checkbox"
                  checked={isSelected(agent.agent_id)}
                  onChange={(e) => {
                    e.stopPropagation();
                    handleToggleAgent(agent, e.target.checked);
                  }}
                  disabled={agent.status === 'unavailable'}
                  className="mt-1 h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />

                <div
                  className={`p-2 rounded-lg ${
                    agent.type === 'computer_use'
                      ? 'bg-blue-100 text-blue-600'
                      : 'bg-gray-100 text-gray-600'
                  }`}
                >
                  {getAgentIcon(agent)}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium">{agent.name}</span>
                    {getStatusBadge(agent.status)}
                  </div>
                  {agent.description && (
                    <p className="text-sm text-gray-500 line-clamp-2">
                      {agent.description}
                    </p>
                  )}
                  {agent.available_tools && agent.available_tools.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {agent.available_tools.slice(0, 5).map((tool) => (
                        <Badge
                          key={tool}
                          className="text-[10px] py-0 px-1.5 bg-gray-50 text-gray-600 border-gray-200"
                        >
                          {tool}
                        </Badge>
                      ))}
                      {agent.available_tools.length > 5 && (
                        <Badge className="text-[10px] py-0 px-1.5 bg-gray-50 text-gray-600 border-gray-200">
                          +{agent.available_tools.length - 5}
                        </Badge>
                      )}
                    </div>
                  )}
                </div>

                {isSelected(agent.agent_id) && onConfigureAgent && (
                  <button
                    onClick={(e: React.MouseEvent) => {
                      e.stopPropagation();
                      onConfigureAgent(agent);
                    }}
                    className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
                  >
                    <Settings className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default RemoteAgentSelector;
