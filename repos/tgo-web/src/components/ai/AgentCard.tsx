import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Pencil, Trash2, MessageCircle, MoreVertical, Copy, Power, Bot } from 'lucide-react';
import AgentToolTag from '@/components/ui/AgentToolTag';
import KnowledgeBaseTag from '@/components/ui/KnowledgeBaseTag';
import WorkflowTag from '@/components/ui/WorkflowTag';
import DeviceTag from '@/components/ui/DeviceTag';
import { generateDefaultAvatar, hasValidAvatar } from '@/utils/avatarUtils';
import { useAIStore } from '@/stores';
import { useToast } from '@/hooks/useToast';
import type { Agent, AgentToolResponse } from '@/types';

interface AgentCardProps {
  agent: Agent;
  onAction: (actionType: string, agent: Agent) => void;
  onToolClick?: (tool: AgentToolResponse) => void;
}

/**
 * Agent card component displaying agent information and actions
 */
const AgentCard: React.FC<AgentCardProps> = ({ agent, onAction, onToolClick }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [showAllCollections, setShowAllCollections] = useState(false);
  const [showAllTools, setShowAllTools] = useState(false);
  const [showAllWorkflows, setShowAllWorkflows] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false);
      }
    };

    if (showMenu) {
      document.addEventListener('mousedown', handleClickOutside);
    } else {
      document.removeEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showMenu]);

  // Get store functions and toast
  const { updateAgent } = useAIStore();
  const { showToast } = useToast();

  // Navigate to chat with this agent
  const handleChatWithAgent = (): void => {
    const channelId = `${agent.id}-agent`;
    navigate(`/chat/1/${channelId}`, {
      state: {
        agentName: agent.name,
        agentAvatar: agent.avatar,
        platform: 'agent'
      }
    });
  };

  const handleAction = (actionType: string): void => {
    setShowMenu(false);
    onAction?.(actionType, agent);
  };

  const handleToggleStatus = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowMenu(false);
    try {
      const newStatus = agent.status === 'active' ? 'inactive' : 'active';
      await updateAgent(agent.id, { status: newStatus });
      showToast('success', t('agents.messages.statusUpdateSuccess', '刷新成功'), t('agents.messages.statusUpdateSuccessDesc', `AI员工 "${agent.name}" 状态已更新`, { name: agent.name }));
    } catch (error) {
      showToast('error', t('agents.messages.statusUpdateFailed', '刷新失败'), t('agents.messages.statusUpdateFailedDesc', '更新AI员工状态时发生错误'));
    }
  };

  const handleToolClick = (tool: AgentToolResponse): void => {
    onToolClick?.(tool);
  };

  const hasValidAvatarUrl = hasValidAvatar(agent.avatar);
  const defaultAvatar = !hasValidAvatarUrl ? generateDefaultAvatar(agent.name, agent.id) : null;

  const getStatusIndicator = (status: string) => {
    switch (status) {
      case 'active':
        return { 
          color: 'bg-green-500', 
          textColor: 'text-green-600 dark:text-green-400',
          bgColor: 'bg-green-50 dark:bg-green-900/20',
          borderColor: 'border-green-200 dark:border-green-800',
          title: t('agents.card.status.active', '运行中') 
        };
      case 'inactive':
        return { 
          color: 'bg-gray-400', 
          textColor: 'text-gray-500 dark:text-gray-400',
          bgColor: 'bg-gray-50 dark:bg-gray-700/30',
          borderColor: 'border-gray-200 dark:border-gray-700',
          title: t('agents.card.status.inactive', '已停止') 
        };
      case 'error':
        return { 
          color: 'bg-red-500', 
          textColor: 'text-red-600 dark:text-red-400',
          bgColor: 'bg-red-50 dark:bg-red-900/20',
          borderColor: 'border-red-200 dark:border-red-800',
          title: t('agents.card.status.error', '错误') 
        };
      default:
        return { 
          color: 'bg-gray-400', 
          textColor: 'text-gray-500 dark:text-gray-400',
          bgColor: 'bg-gray-50 dark:bg-gray-700/30',
          borderColor: 'border-gray-200 dark:border-gray-700',
          title: t('agents.card.status.unknown', '未知') 
        };
    }
  };

  const status = getStatusIndicator(agent.status);

  return (
    <div className="group relative bg-white dark:bg-gray-800 rounded-2xl p-5 flex flex-col justify-between shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 border border-gray-100 dark:border-gray-700 overflow-hidden">
      {/* Background decoration */}
      <div className={`absolute -right-8 -top-8 w-24 h-24 rounded-full opacity-[0.03] dark:opacity-[0.05] ${status.color}`}></div>
      
      <div>
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center space-x-4">
            <div className="relative group/avatar">
              <div className={`absolute -inset-1 rounded-xl opacity-20 group-hover/avatar:opacity-40 transition-opacity duration-300 ${status.color}`}></div>
              {hasValidAvatarUrl ? (
                <img
                  src={agent.avatar}
                  alt={agent.name}
                  className="relative w-12 h-12 rounded-xl object-cover flex-shrink-0 border-2 border-white dark:border-gray-700 shadow-sm"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                    const next = e.currentTarget.nextElementSibling as HTMLElement;
                    if (next) next.style.display = 'flex';
                  }}
                />
              ) : null}
              <div
                className={`relative w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold text-lg border-2 border-white dark:border-gray-700 shadow-sm ${
                  hasValidAvatarUrl ? 'hidden' : ''
                } ${defaultAvatar?.colorClass || 'bg-gradient-to-br from-gray-400 to-gray-500'}`}
                style={{ display: hasValidAvatarUrl ? 'none' : 'flex' }}
              >
                {defaultAvatar?.letter || '?'}
              </div>
              <div className={`absolute -bottom-1 -right-1 w-3.5 h-3.5 rounded-full border-2 border-white dark:border-gray-800 ${status.color}`}></div>
            </div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-gray-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors duration-200">{agent.name}</h3>
              <div className="flex items-center mt-0.5">
                <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-medium border ${status.bgColor} ${status.textColor} ${status.borderColor}`}>
                  {status.title}
                </span>
                <span className="mx-1.5 text-gray-300 dark:text-gray-600">•</span>
                <span className="text-xs text-gray-500 dark:text-gray-400 font-medium truncate max-w-[100px]">{agent.role || t('agents.card.defaultRole', 'AI员工')}</span>
              </div>
            </div>
          </div>
          
          <div className="relative" ref={menuRef}>
            <button 
              onClick={() => setShowMenu(!showMenu)}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <MoreVertical className="w-5 h-5" />
            </button>
            
            {showMenu && (
              <div className="absolute right-0 mt-2 w-40 bg-white dark:bg-gray-800 rounded-xl shadow-xl border border-gray-100 dark:border-gray-700 py-1 z-20 animate-in fade-in zoom-in-95 duration-200">
                <button onClick={() => handleAction('edit')} className="w-full flex items-center px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                  <Pencil className="w-4 h-4 mr-2" /> {t('agents.actions.edit', '编辑')}
                </button>
                <button onClick={() => handleAction('copy')} className="w-full flex items-center px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                  <Copy className="w-4 h-4 mr-2" /> {t('agents.actions.copy', '复制')}
                </button>
                <button onClick={handleToggleStatus} className="w-full flex items-center px-3 py-2 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                  <Power className={`w-4 h-4 mr-2 ${agent.status === 'active' ? 'text-orange-500' : 'text-green-500'}`} /> 
                  {agent.status === 'active' ? t('agents.actions.disable', '停止') : t('agents.actions.enable', '启用')}
                </button>
                <div className="h-px bg-gray-100 dark:bg-gray-700 my-1"></div>
                <button onClick={() => handleAction('delete')} className="w-full flex items-center px-3 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                  <Trash2 className="w-4 h-4 mr-2" /> {t('agents.actions.delete', '删除')}
                </button>
              </div>
            )}
          </div>
        </div>

        <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed mb-4 line-clamp-2 h-10 group-hover:text-gray-700 dark:group-hover:text-gray-300 transition-colors">
          {agent.description || t('agents.card.noDescription', '暂无描述信息')}
        </p>

        <div className="space-y-3">
          {/* Model info */}
          <div className="flex items-center text-[11px] text-gray-500 dark:text-gray-500 bg-gray-50 dark:bg-gray-800/50 px-2 py-1.5 rounded-lg border border-gray-100/50 dark:border-gray-700/50">
            <Bot className="w-3.5 h-3.5 mr-2 opacity-70" />
            <span className="font-mono truncate">{agent.llmModel || 'gemini-1.5-pro'}</span>
          </div>

          {/* 工具显示 */}
          <div className="min-h-[24px]">
            {agent.agentTools && agent.agentTools.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {(showAllTools ? agent.agentTools || [] : (agent.agentTools || []).slice(0, 2)).map((tool) => (
                  <AgentToolTag key={tool.id} tool={tool} onClick={handleToolClick} size="xs" />
                ))}
                {agent.agentTools && agent.agentTools.length > 2 && (
                  <button onClick={() => setShowAllTools(!showAllTools)} className="text-[10px] text-blue-500 hover:text-blue-600 font-medium px-1 underline-offset-2 hover:underline">
                    {showAllTools ? t('agents.actions.collapse', '收起') : `+${agent.agentTools.length - 2}`}
                  </button>
                )}
              </div>
            ) : null}
          </div>

          {/* 工作流显示 */}
          <div className="min-h-[24px]">
            {agent.workflows && agent.workflows.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {(showAllWorkflows ? agent.workflows : agent.workflows.slice(0, 2)).map((workflow) => (
                  <WorkflowTag
                    key={typeof workflow === 'string' ? workflow : workflow.id}
                    workflow={typeof workflow === 'string' ? { id: workflow, name: workflow } : workflow}
                    size="xs"
                    onClick={() => navigate(`/ai/workflows/${typeof workflow === 'string' ? workflow : workflow.id}/edit`)}
                  />
                ))}
                {agent.workflows.length > 2 && (
                  <button onClick={() => setShowAllWorkflows(!showAllWorkflows)} className="text-[10px] text-purple-500 hover:text-purple-600 font-medium px-1 underline-offset-2 hover:underline">
                    {showAllWorkflows ? t('agents.actions.collapse', '收起') : `+${agent.workflows.length - 2}`}
                  </button>
                )}
              </div>
            ) : null}
          </div>

          {/* 知识库标签 */}
          <div className="min-h-[24px]">
            {agent.collections && agent.collections.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {(showAllCollections ? agent.collections : agent.collections.slice(0, 3)).map((collection) => (
                  <KnowledgeBaseTag key={collection.id} name={collection.display_name} size="xs" icon={collection.collection_metadata?.icon} />
                ))}
                {agent.collections.length > 3 && (
                  <button onClick={() => setShowAllCollections(!showAllCollections)} className="text-[10px] text-green-500 hover:text-green-600 font-medium px-1 underline-offset-2 hover:underline">
                    {showAllCollections ? t('agents.actions.collapse', '收起') : `+${agent.collections.length - 3}`}
                  </button>
                )}
              </div>
            ) : null}
          </div>

          {/* 绑定设备 */}
          {agent.boundDevice && (
            <div className="min-h-[24px]">
              <div className="flex flex-wrap gap-1.5">
                <DeviceTag device={agent.boundDevice} size="xs" />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 flex items-center gap-2">
        <button
          onClick={handleChatWithAgent}
          className="flex-1 flex items-center justify-center gap-2 py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl shadow-lg shadow-blue-200 dark:shadow-none transition-all duration-200 active:scale-95"
        >
          <MessageCircle className="w-3.5 h-3.5" />
          {t('agents.card.chatAction', '开始对话')}
        </button>
        <button
          onClick={() => handleAction('edit')}
          className="p-2 bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 rounded-xl border border-gray-100 dark:border-gray-600 transition-all duration-200 hover:bg-blue-50 dark:hover:bg-blue-900/30"
          title={t('agents.actions.edit', '编辑')}
        >
          <Pencil className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export default AgentCard;
