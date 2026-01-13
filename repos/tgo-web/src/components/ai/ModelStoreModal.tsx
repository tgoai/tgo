import React, { useState, useEffect } from 'react';
import { X, Search, Filter, Loader2, Sparkles, Brain, Grid3X3, LogOut, Cpu, Database, Image, Mic } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ModelStoreCard from './ModelStoreCard';
import ModelStoreDetail from './ModelStoreDetail';
import StoreLoginModal from './StoreLoginModal';
import { storeApi } from '@/services/storeApi';
import { useProvidersStore } from '@/stores/providersStore';
import { useStoreAuthStore } from '@/stores/storeAuthStore';
import { useToast } from './ToolToastProvider';
import type { ModelStoreItem, ModelStoreCategory } from '@/types';

interface ModelStoreModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ModelStoreModal: React.FC<ModelStoreModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedModel, setSelectedModel] = useState<ModelStoreItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [installStep, setInstallStep] = useState<'idle' | 'verify' | 'sync' | 'done'>('idle');
  const [loading, setLoading] = useState(true);
  const [models, setModels] = useState<ModelStoreItem[]>([]);
  const [installedModelNames, setInstalledModelNames] = useState<string[]>([]);
  const [categories, setCategories] = useState<ModelStoreCategory[]>([]);
  const [_total, setTotal] = useState(0);

  const { loadProviders } = useProvidersStore();
  const { isAuthenticated, user, bindToProject, logout } = useStoreAuthStore();
  const { i18n } = useTranslation();
  const currentLang = i18n.language.startsWith('zh') ? 'zh' : 'en';

  // Load categories from Model Store API
  const fetchCategories = async () => {
    try {
      const data = await storeApi.getModelCategories();
      const mappedCategories: ModelStoreCategory[] = [
        { 
          id: 'all', 
          slug: 'all', 
          name_zh: t('store.model.allModels'), 
          name_en: 'All Models', 
          icon: 'Grid3X3'
        },
        ...data.map((cat: any) => ({
          id: cat.id,
          slug: cat.slug,
          name_zh: cat.name_zh,
          name_en: cat.name_en,
          icon: cat.icon || 'Cpu'
        }))
      ];
      setCategories(mappedCategories);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  // Load models from Model Store API
  const fetchModels = async () => {
    setLoading(true);
    try {
      // Fetch models from store and installed models from local API in parallel
      const [data, installedNames] = await Promise.all([
        storeApi.getModels({
          category: selectedCategory === 'all' ? undefined : selectedCategory,
          search: debouncedSearchQuery || undefined,
        }),
        storeApi.getInstalledModels()
      ]);
      
      setInstalledModelNames(installedNames || []);
      
      // Override is_installed status with local source of truth
      const mergedModels = (data?.items || []).map((m: any) => ({
        ...m,
        is_installed: installedNames.includes(m.name)
      }));

      setModels(mergedModels);
      setTotal(data?.total || 0);
    } catch (error) {
      console.error('Failed to fetch models from store:', error);
      showToast('error', t('common.error'), t('tools.store.model.fetchFailed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchCategories();
    }
  }, [isOpen]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    if (isOpen) {
      fetchModels();
    }
  }, [isOpen, selectedCategory, debouncedSearchQuery]);

  const handleModelClick = async (model: ModelStoreItem) => {
    // Initial selection based on current item
    setSelectedModel({
      ...model,
      is_installed: installedModelNames.includes(model.name)
    });
    setIsDetailOpen(true);
    
    // Asynchronously fetch full details if needed
    try {
      const fullModel = await storeApi.getModel(model.id);
      if (fullModel) {
        setSelectedModel({
          ...fullModel,
          is_installed: installedModelNames.includes(fullModel.name)
        });
      }
    } catch (error) {
      console.error('Failed to fetch model detail:', error);
    }
  };

  const handleInstall = async (e: React.MouseEvent | ModelStoreItem, modelInput?: ModelStoreItem) => {
    const model = modelInput || (e as ModelStoreItem);
    if (e && (e as React.MouseEvent).stopPropagation) {
      (e as React.MouseEvent).stopPropagation();
    }

    // AUTH CHECK
    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }

    setInstallingId(model.id);
    setInstallStep('verify');
    
    try {
      // 1. Ensure credentials are bound to project
      await bindToProject();
      setInstallStep('sync');

      if (model.is_installed) {
        // Uninstall
        await storeApi.uninstallModel(model.id);
        showToast('success', t('tools.store.model.uninstallSuccess'), t('tools.store.model.uninstallSuccessMessage', { name: model.title_zh || model.name }));
      } else {
        // Install
        await storeApi.installModel(model.id);
        showToast('success', t('tools.store.model.installSuccess'), t('tools.store.model.installSuccessMessage', { name: model.title_zh || model.name }));
      }
      
      setInstallStep('done');
      
      // Update local state based on operation
      const modelName = model.name;
      setInstalledModelNames(prev => {
        if (model.is_installed) {
          return prev.filter(name => name !== modelName);
        } else {
          return [...prev, modelName];
        }
      });

      // Update models list state for UI feedback
      setModels(prev => prev.map(m => m.id === model.id ? { ...m, is_installed: !m.is_installed } : m));
      
      if (selectedModel?.id === model.id) {
        setSelectedModel(prev => prev ? { ...prev, is_installed: !prev.is_installed } : null);
      }

      // Refresh local providers list
      await loadProviders();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || t('common.saveFailed');
      showToast('error', t('common.error'), errorMsg);
    } finally {
      setInstallingId(null);
      setInstallStep('idle');
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
                  {t('tools.store.model.title')}
                </h2>
              </div>

              <nav className="space-y-1">
                {categories.map((cat: ModelStoreCategory) => {
                  const IconComponent = cat.icon ? ({
                    Grid3X3,
                    Brain,
                    Cpu,
                    Database,
                    Image,
                    Mic
                  } as any)[cat.icon] || Filter : Filter;

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
          <div className="flex-1 flex flex-col min-w-0">
            {/* Header */}
            <header className="px-8 py-6 flex items-center justify-between gap-6 border-b border-gray-100 dark:border-gray-800 bg-white/50 dark:bg-gray-900/50 backdrop-blur-xl">
              <div className="relative flex-1 max-w-2xl group">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 group-focus-within:text-blue-500 transition-colors" />
                <input 
                  type="text"
                  placeholder={t('tools.store.model.searchPlaceholder')}
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
                    {t('tools.store.loginNow')}
                  </button>
                ) : (
                  <div className="hidden sm:flex items-center gap-3 pl-4 border-l border-gray-200 dark:border-gray-800">
                    <div className="text-right">
                      <div className="text-xs font-black text-gray-900 dark:text-gray-100 truncate max-w-[100px]">
                        {user?.name || user?.email}
                      </div>
                      <div className="text-[10px] text-blue-600 font-bold uppercase tracking-tighter">
                        {t('tools.store.balance')}: ${user?.credits?.toFixed(2)}
                      </div>
                    </div>
                    <div className="relative group">
                      <div className="w-9 h-9 rounded-xl bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 flex items-center justify-center font-bold text-sm cursor-pointer">
                        {user?.name?.charAt(0).toUpperCase() || user?.email?.charAt(0).toUpperCase()}
                      </div>
                      <button 
                        onClick={() => logout()}
                        className="absolute top-full right-0 mt-2 p-2 bg-white dark:bg-gray-800 shadow-xl rounded-xl border border-gray-100 dark:border-gray-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all flex items-center gap-2 text-xs font-bold text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 whitespace-nowrap z-50"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        {t('tools.store.logout')}
                      </button>
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

            {/* Model Grid */}
            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
              <div className="max-w-[1200px] mx-auto">
                {loading ? (
                  <div className="flex flex-col items-center justify-center h-[500px] gap-4">
                    <Loader2 className="w-10 h-10 text-blue-600 animate-spin" />
                    <p className="text-sm font-bold text-gray-400 animate-pulse">{t('tools.store.model.loading')}</p>
                  </div>
                ) : !models || models.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-[500px] text-center">
                    <div className="w-20 h-20 rounded-3xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-gray-300 dark:text-gray-700 mb-6">
                      <Search className="w-10 h-10" />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-gray-100 mb-2">{t('tools.store.model.noResults')}</h3>
                    <p className="text-gray-500 dark:text-gray-400">{t('tools.store.model.noResultsDesc')}</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    {models.map(model => (
                      <ModelStoreCard 
                        key={model.id} 
                        model={model} 
                        onClick={handleModelClick}
                        onInstall={(e) => handleInstall(e, model)}
                        isInstalled={installedModelNames.includes(model.name)}
                        installingId={installingId}
                        installStep={installStep}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Model Detail Panel */}
      <ModelStoreDetail 
        model={selectedModel}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
        onInstall={(model) => handleInstall(model)}
        isInstalled={selectedModel ? installedModelNames.includes(selectedModel.name) : false}
        installingId={installingId}
        installStep={installStep}
      />

      {/* Login Modal */}
      <StoreLoginModal 
        isOpen={showLoginModal}
        onClose={() => setShowLoginModal(false)}
      />
    </div>
  );
};

export default ModelStoreModal;
