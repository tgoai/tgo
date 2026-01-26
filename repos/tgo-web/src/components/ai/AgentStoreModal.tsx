import React, { useState, useMemo, useCallback } from 'react';
import { Bot } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import AgentStoreCard from './AgentStoreCard';
import AgentStoreDetail from './AgentStoreDetail';
import ModelStoreDetail from './ModelStoreDetail';
import ToolStoreDetail from './ToolStoreDetail';
import StoreLoginModal from './StoreLoginModal';
import AgentDependencyModal from './AgentDependencyModal';
import { storeApi } from '@/services/storeApi';
import { useAIStore } from '@/stores';
import { useStoreAuthStore } from '@/stores/storeAuthStore';
import { useToast } from '@/hooks/useToast';
import type { AgentStoreItem, AgentStoreCategory, AgentDependencyCheckResponse } from '@/types';

// New Base Components and Hook
import { 
  StoreModalBase, 
  StoreSidebar, 
  StoreHeader, 
  StoreUserStatus, 
  StoreContentArea 
} from './store';
import { useStoreModal } from './store/hooks/useStoreModal';

interface AgentStoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInstalled?: () => void;
}

const AgentStoreModal: React.FC<AgentStoreModalProps> = ({ isOpen, onClose, onInstalled }) => {
  const { t } = useTranslation();
  const { showSuccess, showError } = useToast();
  
  const [selectedAgent, setSelectedAgent] = useState<AgentStoreItem | null>(null);
  const [selectedModel, setSelectedModel] = useState<any | null>(null);
  const [selectedTool, setSelectedTool] = useState<any | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isModelDetailOpen, setIsModelDetailOpen] = useState(false);
  const [isToolDetailOpen, setIsToolDetailOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showDependencyModal, setShowDependencyModal] = useState(false);
  const [dependencyData, setDependencyData] = useState<AgentDependencyCheckResponse | null>(null);
  const [installingId, setInstallingId] = useState<string | null>(null);

  const { agents: localAgents, loadAgents } = useAIStore();
  const { isAuthenticated, bindToProject } = useStoreAuthStore();

  const fetchCategories = useCallback(async () => {
    const data = await storeApi.getAgentCategories();
    return [
      { 
        id: 'all', 
        slug: 'all', 
        name_zh: '全部员工', 
        name_en: 'All Agents', 
        icon: 'Grid3X3'
      },
      ...data
    ];
  }, []);

  const {
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    loading,
    items: agents,
    categories
  } = useStoreModal<AgentStoreItem, AgentStoreCategory>({
    isOpen,
    fetchItems: storeApi.getAgents,
    fetchCategories,
    onUnauthorized: () => setShowLoginModal(true)
  });

  // Check if an agent is already installed
  const installedAgentNames = useMemo(() => {
    return new Set(localAgents.map(a => a.name.toLowerCase()));
  }, [localAgents]);

  const handleAgentClick = async (agent: AgentStoreItem) => {
    setSelectedAgent(agent);
    setIsDetailOpen(true);
  };

  const handleModelClick = async (modelId: string) => {
    try {
      const model = await storeApi.getModel(modelId);
      setSelectedModel(model);
      setIsModelDetailOpen(true);
    } catch (error) {
      console.error('Failed to fetch model detail:', error);
    }
  };

  const handleToolClick = async (toolId: string) => {
    try {
      const tool = await storeApi.getTool(toolId);
      setSelectedTool(tool);
      setIsToolDetailOpen(true);
    } catch (error) {
      console.error('Failed to fetch tool detail:', error);
    }
  };

  const handleInstall = async (e: React.MouseEvent | AgentStoreItem, agentInput?: AgentStoreItem) => {
    const agent = agentInput || (e as AgentStoreItem);
    if (e && (e as React.MouseEvent).stopPropagation) {
      (e as React.MouseEvent).stopPropagation();
    }

    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }

    if (installedAgentNames.has(agent.title_zh?.toLowerCase() || agent.name.toLowerCase())) {
      showSuccess(t('common.info'), t('agents.store.alreadyInstalled', '该员工已在团队中'));
      return;
    }

    setInstallingId(agent.id);
    
    try {
      await bindToProject();
      const deps = await storeApi.checkAgentDependencies(agent.id);
      
      if (deps.missing_tools.length > 0 || deps.missing_model) {
        setDependencyData(deps);
        setShowDependencyModal(true);
        setInstallingId(null);
        return;
      }
      
      await storeApi.installAgent(agent.id);
      await loadAgents();
      if (onInstalled) onInstalled();
    } catch (error) {
      showError(t('common.error'), t('agents.store.installFailed', '招聘失败，请重试'));
    } finally {
      setInstallingId(null);
    }
  };

  const handleConfirmDependencies = async (selectedToolIds: string[], installModel: boolean) => {
    if (!dependencyData) return;
    
    setInstallingId(dependencyData.agent.id);
    try {
      await storeApi.installAgent(dependencyData.agent.id, {
        install_tool_ids: selectedToolIds,
        install_model: installModel
      });
      
      setShowDependencyModal(false);
      await loadAgents();
      if (onInstalled) onInstalled();
    } catch (error) {
      showError(t('common.error'), t('agents.store.installFailed', '招聘失败，请重试'));
    } finally {
      setInstallingId(null);
    }
  };

  return (
    <>
      <StoreModalBase isOpen={isOpen} onClose={onClose}
        sidebar={
          <StoreSidebar 
            title={t('agents.store.title', '员工商店')}
            icon={<Bot className="w-5 h-5" />}
            categories={categories}
            selectedCategory={selectedCategory}
            onCategoryChange={setSelectedCategory}
            themeColor="indigo"
          />
        }
        header={
          <StoreHeader 
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            searchPlaceholder={t('agents.store.searchPlaceholder', '搜索员工名称或职责...')}
            onClose={onClose}
            themeColor="indigo"
            userStatus={
              <StoreUserStatus 
                themeColor="indigo" 
                onLoginClick={() => setShowLoginModal(true)} 
              />
            }
          />
        }
      >
        <StoreContentArea 
          loading={loading} 
          isEmpty={!agents || agents.length === 0}
          emptyIcon={<Bot className="w-10 h-10" />}
          emptyTitle={t('agents.store.noResults', '未找到匹配的员工')}
          themeColor="indigo"
        >
          {agents.map(agent => (
            <AgentStoreCard 
              key={agent.id} 
              agent={agent} 
              onClick={handleAgentClick}
              onInstall={handleInstall}
              isInstalled={installedAgentNames.has(agent.title_zh?.toLowerCase() || agent.name.toLowerCase())}
            />
          ))}
        </StoreContentArea>
      </StoreModalBase>

      <AgentStoreDetail 
        agent={selectedAgent}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        onInstall={(agent) => handleInstall(agent)}
        isInstalled={selectedAgent ? installedAgentNames.has(selectedAgent.title_zh?.toLowerCase() || selectedAgent.name.toLowerCase()) : false}
        installingId={installingId}
        onModelClick={handleModelClick}
        onToolClick={handleToolClick}
      />

      <ModelStoreDetail 
        model={selectedModel}
        isOpen={isModelDetailOpen}
        onClose={() => setIsModelDetailOpen(false)}
        onInstall={async (model) => {
          if (!isAuthenticated) {
            setShowLoginModal(true);
            return;
          }
          try {
            await bindToProject();
            await storeApi.installModel(model.id);
          } catch (error) {
            showError(t('common.error'), t('common.saveFailed'));
          }
        }}
        isInstalled={false}
        installingId={null}
        installStep="idle"
      />

      <ToolStoreDetail 
        tool={selectedTool}
        isOpen={isToolDetailOpen}
        onClose={() => setIsToolDetailOpen(false)}
        onInstall={async (tool) => {
          if (!isAuthenticated) {
            setShowLoginModal(true);
            return;
          }
          try {
            await bindToProject();
            await storeApi.installTool(tool.id);
          } catch (error) {
            showError(t('common.error'), t('common.saveFailed'));
          }
        }}
        isInstalled={false}
        installingId={null}
      />

      <StoreLoginModal 
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
      />

      <AgentDependencyModal
        isOpen={showDependencyModal}
        onClose={() => setShowDependencyModal(false)}
        dependencyData={dependencyData}
        onConfirm={handleConfirmDependencies}
        isInstalling={installingId === (dependencyData?.agent.id)}
      />
    </>
  );
};

export default AgentStoreModal;
