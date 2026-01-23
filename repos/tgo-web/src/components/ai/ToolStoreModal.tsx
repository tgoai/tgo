import React, { useState, useMemo, useEffect } from 'react';
import { X, Search, Filter, Loader2, Sparkles, Brain, Wrench, Bot, Puzzle, Package, Grid3X3, LogOut, CreditCard } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ToolStoreCard from './ToolStoreCard';
import ToolStoreDetail from './ToolStoreDetail';
import StoreLoginModal from './StoreLoginModal';
import { storeApi } from '@/services/storeApi';
import { useProjectToolsStore } from '@/stores/projectToolsStore';
import { useStoreAuthStore } from '@/stores/storeAuthStore';
import { useToast } from './ToolToastProvider';
import type { ToolStoreItem, ToolStoreCategory } from '@/types';

interface ToolStoreModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ToolStoreModal: React.FC<ToolStoreModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedTool, setSelectedTool] = useState<ToolStoreItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tools, setTools] = useState<ToolStoreItem[]>([]);
  const [categories, setCategories] = useState<ToolStoreCategory[]>([]);
  const [_total, setTotal] = useState(0);

  const { aiTools, loadTools } = useProjectToolsStore();
  const { isAuthenticated, user, bindToProject, logout, verifySession, isVerifying } = useStoreAuthStore();
  const { i18n } = useTranslation();
  const currentLang = i18n.language.startsWith('zh') ? 'zh' : 'en';

  // Load categories from Tool Store API
  const fetchCategories = async () => {
    try {
      const data = await storeApi.getToolCategories();
      const mappedCategories: ToolStoreCategory[] = [
        { 
          id: 'all', 
          slug: 'all', 
          name_zh: '全部工具', 
          name_en: 'All Tools', 
          icon: 'Grid3X3', 
          label: '全部工具' 
        },
        ...data.map((cat: any) => ({
          id: cat.id,
          slug: cat.slug,
          name_zh: cat.name_zh,
          name_en: cat.name_en,
          icon: cat.icon || 'Package',
          label: cat.name_zh
        }))
      ];
      setCategories(mappedCategories);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  // Load tools from Tool Store API
  const fetchTools = async () => {
    setLoading(true);
    try {
      const data = await storeApi.getTools({
        category: selectedCategory === 'all' ? undefined : selectedCategory,
        search: searchQuery || undefined,
      });
      
      // 前端简单增强搜索，如果后端不支持多语言搜索的话
      // 实际上后端 ilike 应该支持中文了
      setTools(data?.items || []);
      setTotal(data?.total || 0);
    } catch (error) {
      console.error('Failed to fetch tools from store:', error);
      showToast('error', t('common.error'), t('tools.store.fetchFailed', '获取商店工具失败'));
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
      fetchTools();
    }
  }, [isOpen, selectedCategory, searchQuery]);

  // Check if a tool is already installed in the project
  const installedToolNames = useMemo(() => {
    return new Set(aiTools.map(t => t.name.toLowerCase()));
  }, [aiTools]);

  const handleToolClick = async (tool: ToolStoreItem) => {
    // 先显示基础信息
    setSelectedTool(tool);
    setIsDetailOpen(true);
    
    // 异步加载完整详情 (包括 methods 等)
    try {
      const fullTool = await storeApi.getTool(tool.id);
      if (fullTool) {
        setSelectedTool(fullTool);
      }
    } catch (error) {
      console.error('Failed to fetch tool detail:', error);
    }
  };

  const handleInstall = async (e: React.MouseEvent | ToolStoreItem, toolInput?: ToolStoreItem) => {
    const tool = toolInput || (e as ToolStoreItem);
    if (e && (e as React.MouseEvent).stopPropagation) {
      (e as React.MouseEvent).stopPropagation();
    }

    // AUTH CHECK
    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }

    if (installedToolNames.has(tool.name.toLowerCase())) {
      showToast('info', t('tools.store.installed', '已安装'), t('tools.store.installSuccessMessage', { name: tool.name }));
      return;
    }

    setInstallingId(tool.id);
    
    try {
      // 1. 确保凭证已绑定到项目
      await bindToProject();

      // 2. 在工具商店安装
      await storeApi.installTool(tool.id);
      
      showToast('success', t('tools.store.installSuccess', '安装成功'), t('tools.store.installSuccessMessage', { name: tool.name }));
      
      // Refresh installed tools list
      await loadTools(false);
    } catch (error) {
      showToast('error', t('common.error', '错误'), t('common.saveFailed', '保存失败'));
    } finally {
      setInstallingId(null);
    }
  };

  const handleRecharge = async () => {
    try {
      const config = await storeApi.getStoreConfig();
      const rechargeUrl = `${config.store_web_url}/account?recharge=true`;
      window.open(rechargeUrl, '_blank');
    } catch (e) {
      // 降级使用默认地址
      window.open('https://store.tgo.ai/account?recharge=true', '_blank');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 md:p-10">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-gray-900/60 backdrop-blur-md animate-in fade-in duration-300"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-[1400px] h-full max-h-[900px] bg-[#f8fafc] dark:bg-gray-950 rounded-[2.5rem] shadow-2xl flex flex-col overflow-hidden border border-white/10 animate-in zoom-in-95 slide-in-from-bottom-10 duration-500 ease-out">
        
        {/* Sidebar + Main Content */}
        <div className="flex flex-1 overflow-hidden">
          
          {/* Sidebar - Categories */}
          <aside className="w-72 bg-white/50 dark:bg-gray-900/50 border-r border-gray-200/50 dark:border-gray-800/50 hidden lg:flex flex-col">
            <div className="p-8">
              <div className="flex items-center gap-2 mb-8">
                <div className="w-10 h-10 rounded-2xl bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-200 dark:shadow-none">
                  <Sparkles className="w-5 h-5" />
                </div>
                <h2 className="text-xl font-black text-gray-900 dark:text-gray-100 tracking-tight">
                  {t('tools.toolStore', '工具商店')}
                </h2>
              </div>

              <nav className="space-y-1">
                {categories.map((cat: ToolStoreCategory) => {
                  const IconComponent = ({
                    Grid3X3,
                    Brain,
                    Wrench,
                    Bot,
                    Puzzle,
                    Package
                  } as any)[cat.icon] || Filter;

                  const displayName = currentLang === 'zh' ? cat.name_zh : (cat.name_en || cat.name_zh);

                  return (
                    <button
                      key={cat.id}
                      onClick={() => setSelectedCategory(cat.slug)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-bold transition-all ${
                        selectedCategory === cat.slug
                          ? 'bg-blue-600 text-white shadow-lg shadow-blue-100 dark:shadow-none'
                          : 'text-gray-500 hover:bg-white dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-100'
                      }`}
                    >
                      <IconComponent className={`w-4 h-4 ${selectedCategory === cat.slug ? 'opacity-100' : 'opacity-50'}`} />
                      {displayName}
                    </button>
                  );
                })}
              </nav>
            </div>
          </aside>

          {/* Main Area */}
          <div className="flex-1 flex flex-col min-w-0 relative">
            {/* Header */}
            <header className="px-8 py-6 flex items-center justify-between gap-6 border-b border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-gray-900/50 backdrop-blur-xl sticky top-0 z-20">
              <div className="relative flex-1 max-w-2xl group">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                <input 
                  type="text"
                  placeholder={t('tools.store.searchPlaceholder', '搜索工具、作者或标签...')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-12 pr-4 py-3 bg-gray-100 dark:bg-gray-800 border-transparent focus:bg-white dark:focus:bg-gray-800 focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 rounded-2xl text-sm font-medium transition-all outline-none"
                />
              </div>

              <div className="flex items-center gap-4">
                {/* User Status */}
                {!isAuthenticated ? (
                  <button 
                    onClick={() => setShowLoginModal(true)}
                    className="hidden sm:flex items-center gap-2 px-4 py-2 text-sm font-bold text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-xl transition-all"
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
                    <div 
                      className="text-right cursor-pointer hover:opacity-80 transition-opacity"
                      onClick={() => window.open('http://store.tgo.ai/', '_blank')}
                    >
                      <div className="text-xs font-black text-gray-900 dark:text-gray-100 truncate max-w-[100px]">
                        {user?.name || user?.email}
                      </div>
                      <div className="text-[10px] text-blue-600 font-bold uppercase tracking-tighter">
                        Balance: ${user?.credits?.toFixed(2)}
                      </div>
                    </div>
                    <div className="relative group">
                      <div 
                        className="w-9 h-9 rounded-xl bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-sm cursor-pointer hover:opacity-80 transition-opacity"
                        onClick={() => window.open('http://store.tgo.ai/', '_blank')}
                      >
                        {user?.name?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase()}
                      </div>
                      <div className="absolute top-full right-0 mt-2 p-1 bg-white dark:bg-gray-800 shadow-xl rounded-xl border border-gray-100 dark:border-gray-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all flex flex-col gap-1 z-50 min-w-[120px]">
                        <button 
                          onClick={handleRecharge}
                          className="w-full p-2 flex items-center gap-2 text-xs font-bold text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded-lg transition-colors"
                        >
                          <CreditCard className="w-3.5 h-3.5" />
                          {t('tools.store.recharge', '充值')}
                        </button>
                        <button 
                          onClick={() => logout()}
                          className="w-full p-2 flex items-center gap-2 text-xs font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                        >
                          <LogOut className="w-3.5 h-3.5" />
                          {t('tools.store.logout')}
                        </button>
                      </div>
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

            {/* Tool Grid */}
            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
              <div className="max-w-[1200px] mx-auto">
                {loading ? (
                  <div className="flex flex-col items-center justify-center h-[500px] gap-4">
                    <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                    <p className="text-sm font-bold text-gray-400 animate-pulse">{t('common.loading', '加载中...')}</p>
                  </div>
                ) : !tools || tools.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-[500px] text-center">
                    <div className="w-20 h-20 rounded-3xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-gray-300 dark:text-gray-700 mb-6">
                      <Search className="w-10 h-10" />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">{t('tools.store.noResults', '未找到匹配的工具')}</h3>
                    <p className="text-gray-500 dark:text-gray-400">{t('tools.store.noResultsDesc', '试试搜索其他关键词或切换分类')}</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {tools.map(tool => (
                      <ToolStoreCard 
                        key={tool.id} 
                        tool={tool} 
                        onClick={handleToolClick}
                        onInstall={handleInstall}
                        isInstalled={installedToolNames.has(tool.name.toLowerCase())}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tool Detail Panel */}
      <ToolStoreDetail 
        tool={selectedTool}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        onInstall={(tool) => handleInstall(tool)}
        isInstalled={selectedTool ? installedToolNames.has(selectedTool.name.toLowerCase()) : false}
        installingId={installingId}
      />

      {/* Login Modal */}
      <StoreLoginModal 
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
      />
    </div>
  );
};

export default ToolStoreModal;
