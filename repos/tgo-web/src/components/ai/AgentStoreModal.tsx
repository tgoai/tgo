import React, { useState, useMemo, useEffect } from 'react';
import { X, Search, Loader2, Bot, Package } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import AgentStoreCard from './AgentStoreCard';
import AgentStoreDetail from './AgentStoreDetail';
import StoreLoginModal from './StoreLoginModal';
import AgentDependencyModal from './AgentDependencyModal';
import { storeApi } from '@/services/storeApi';
import { useAIStore } from '@/stores';
import { useStoreAuthStore } from '@/stores/storeAuthStore';
import { useToast } from '@/hooks/useToast';
import type { AgentStoreItem, AgentStoreCategory, AgentDependencyCheckResponse } from '@/types';

interface AgentStoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInstalled?: () => void;
}

const AgentStoreModal: React.FC<AgentStoreModalProps> = ({ isOpen, onClose, onInstalled }) => {
  const { t, i18n } = useTranslation();
  const { showSuccess, showError } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedAgent, setSelectedAgent] = useState<AgentStoreItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showDependencyModal, setShowDependencyModal] = useState(false);
  const [dependencyData, setDependencyData] = useState<AgentDependencyCheckResponse | null>(null);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [agents, setAgents] = useState<AgentStoreItem[]>([]);
  const [categories, setCategories] = useState<AgentStoreCategory[]>([]);

  const { agents: localAgents, loadAgents } = useAIStore();
  const { isAuthenticated, user, bindToProject, verifySession, isVerifying } = useStoreAuthStore();
  const currentLang = i18n.language.startsWith('zh') ? 'zh' : 'en';

  // Load categories from Store API
  const fetchCategories = async () => {
    try {
      const data = await storeApi.getAgentCategories();
      const mappedCategories: AgentStoreCategory[] = [
        { 
          id: 'all', 
          slug: 'all', 
          name_zh: '全部员工', 
          name_en: 'All Agents', 
          icon: 'Grid3X3'
        },
        ...data
      ];
      setCategories(mappedCategories);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  // Load agents from Store API
  const fetchAgents = async () => {
    setLoading(true);
    try {
      const data = await storeApi.getAgents({
        category: selectedCategory === 'all' ? undefined : selectedCategory,
        search: searchQuery || undefined,
      });
      setAgents(data?.items || []);
    } catch (error) {
      console.error('Failed to fetch agents from store:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchCategories();

      // 如果显示已登录，主动验证一次会话有效性
      if (isAuthenticated) {
        verifySession();
      }
    }
  }, [isOpen]);

  // 监听全局未授权事件
  useEffect(() => {
    const handleUnauthorized = () => {
      if (isOpen) {
        setShowLoginModal(true);
      }
    };
    window.addEventListener('store-unauthorized', handleUnauthorized);
    return () => window.removeEventListener('store-unauthorized', handleUnauthorized);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      fetchAgents();
    }
  }, [isOpen, selectedCategory, searchQuery]);

  // Check if an agent is already installed
  const installedAgentNames = useMemo(() => {
    return new Set(localAgents.map(a => a.name.toLowerCase()));
  }, [localAgents]);

  const handleAgentClick = async (agent: AgentStoreItem) => {
    setSelectedAgent(agent);
    setIsDetailOpen(true);
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
      
      // 1. 检查依赖
      const deps = await storeApi.checkAgentDependencies(agent.id);
      
      // 2. 如果有缺失依赖，显示确认弹窗
      if (deps.missing_tools.length > 0 || deps.missing_model) {
        setDependencyData(deps);
        setShowDependencyModal(true);
        setInstallingId(null); // 弹窗期间不显示全局 loading
        return;
      }
      
      // 3. 无缺失依赖，直接安装
      await storeApi.installAgent(agent.id);
      
      showSuccess(t('common.success'), t('agents.store.installSuccess', '成功招聘到一名新员工'));
      
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
      
      showSuccess(t('common.success'), t('agents.store.installSuccess', '成功招聘到一名新员工'));
      
      setShowDependencyModal(false);
      await loadAgents();
      if (onInstalled) onInstalled();
    } catch (error) {
      showError(t('common.error'), t('agents.store.installFailed', '招聘失败，请重试'));
    } finally {
      setInstallingId(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-10">
      <div 
        className="absolute inset-0 bg-gray-900/60 backdrop-blur-md animate-in fade-in duration-300"
        onClick={onClose}
      />

      <div className="relative w-full max-w-[1400px] h-full max-h-[900px] bg-[#f8fafc] dark:bg-gray-950 rounded-[2.5rem] shadow-2xl flex flex-col overflow-hidden border border-white/10 animate-in zoom-in-95 slide-in-from-bottom-10 duration-500 ease-out">
        
        <div className="flex flex-1 overflow-hidden">
          
          <aside className="w-72 bg-white/50 dark:bg-gray-900/50 border-r border-gray-200/50 dark:border-gray-800/50 hidden lg:flex flex-col">
            <div className="p-8">
              <div className="flex items-center gap-2 mb-8">
                <div className="w-10 h-10 rounded-2xl bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-200 dark:shadow-none">
                  <Bot className="w-5 h-5" />
                </div>
                <h2 className="text-xl font-black text-gray-900 dark:text-gray-100 tracking-tight">
                  {t('agents.store.title', '员工商店')}
                </h2>
              </div>

              <nav className="space-y-1">
                {categories.map((cat) => {
                  const isActive = selectedCategory === cat.slug;
                  const name = currentLang === 'zh' ? cat.name_zh : (cat.name_en || cat.name_zh);

                  return (
                    <button
                      key={cat.id}
                      onClick={() => setSelectedCategory(cat.slug)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-bold transition-all ${
                        isActive
                          ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-100 dark:shadow-none'
                          : 'text-gray-500 hover:bg-white dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100'
                      }`}
                    >
                      <Package className={`w-4 h-4 ${isActive ? 'opacity-100' : 'opacity-50'}`} />
                      {name}
                    </button>
                  );
                })}
              </nav>
            </div>
          </aside>

          <div className="flex-1 flex flex-col min-w-0">
            <header className="px-8 py-6 flex items-center justify-between gap-6 border-b border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-gray-900/50 backdrop-blur-xl">
              <div className="relative flex-1 max-w-2xl group">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-indigo-500 transition-colors" />
                <input 
                  type="text"
                  placeholder={t('agents.store.searchPlaceholder', '搜索员工名称或职责...')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-12 pr-4 py-3 bg-gray-100 dark:bg-gray-800 border-transparent focus:bg-white dark:focus:bg-gray-800 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 rounded-2xl text-sm font-medium transition-all outline-none"
                />
              </div>

              <div className="flex items-center gap-4">
                {!isAuthenticated ? (
                  <button 
                    onClick={() => setShowLoginModal(true)}
                    className="hidden sm:flex items-center gap-2 px-4 py-2 text-sm font-bold text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-xl transition-all"
                  >
                    {t('tools.store.loginNow', '立即登录')}
                  </button>
                ) : isVerifying ? (
                  <div className="hidden sm:flex items-center gap-3 pl-4 border-l border-gray-200 dark:border-gray-800 animate-pulse">
                    <div className="w-20 h-8 bg-gray-100 dark:bg-gray-800 rounded-lg"></div>
                    <div className="w-9 h-9 rounded-xl bg-gray-100 dark:bg-gray-800"></div>
                  </div>
                ) : (
                  <div className="hidden sm:flex items-center gap-3 pl-4 border-l border-gray-200 dark:border-gray-800">
                    <div className="text-right">
                      <div className="text-xs font-black text-gray-900 dark:text-gray-100 truncate max-w-[100px]">
                        {user?.name || user?.email}
                      </div>
                      <div className="text-[10px] text-indigo-600 font-bold uppercase tracking-tighter">
                        Balance: ${user?.credits?.toFixed(2)}
                      </div>
                    </div>
                    <div 
                      className="w-9 h-9 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center font-bold text-sm"
                    >
                      {user?.name?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase()}
                    </div>
                  </div>
                )}

                <button 
                  onClick={onClose}
                  className="p-3 bg-white dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-2xl text-gray-400 hover:text-gray-600 transition-all shadow-sm active:scale-90"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </header>

            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
              <div className="max-w-[1200px] mx-auto">
                {loading ? (
                  <div className="flex flex-col items-center justify-center h-[500px] gap-4">
                    <Loader2 className="w-10 h-10 text-indigo-600 animate-spin" />
                    <p className="text-sm font-bold text-gray-400 animate-pulse">{t('common.loading', '加载中...')}</p>
                  </div>
                ) : !agents || agents.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-[500px] text-center">
                    <div className="w-20 h-20 rounded-3xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-gray-300 dark:text-gray-700 mb-6">
                      <Bot className="w-10 h-10" />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">{t('agents.store.noResults', '未找到匹配的员工')}</h3>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {agents.map(agent => (
                      <AgentStoreCard 
                        key={agent.id} 
                        agent={agent} 
                        onClick={handleAgentClick}
                        onInstall={handleInstall}
                        isInstalled={installedAgentNames.has(agent.title_zh?.toLowerCase() || agent.name.toLowerCase())}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <AgentStoreDetail 
        agent={selectedAgent}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        onInstall={(agent) => handleInstall(agent)}
        isInstalled={selectedAgent ? installedAgentNames.has(selectedAgent.title_zh?.toLowerCase() || selectedAgent.name.toLowerCase()) : false}
        installingId={installingId}
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
    </div>
  );
};

export default AgentStoreModal;
