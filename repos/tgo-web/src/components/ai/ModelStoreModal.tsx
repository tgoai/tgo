import React, { useState, useEffect, useCallback } from 'react';
import { Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ModelStoreCard from './ModelStoreCard';
import ModelStoreDetail from './ModelStoreDetail';
import StoreLoginModal from './StoreLoginModal';
import { storeApi } from '@/services/storeApi';
import { useProvidersStore } from '@/stores/providersStore';
import { useStoreAuthStore } from '@/stores/storeAuthStore';
import { useToast } from './ToolToastProvider';
import type { ModelStoreItem, ModelStoreCategory } from '@/types';

// New Base Components and Hook
import { 
  StoreModalBase, 
  StoreSidebar, 
  StoreHeader, 
  StoreUserStatus, 
  StoreContentArea 
} from './store';
import { useStoreModal } from './store/hooks/useStoreModal';

interface ModelStoreModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ModelStoreModal: React.FC<ModelStoreModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  
  const [selectedModel, setSelectedModel] = useState<ModelStoreItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [installingId, setInstallingId] = useState<string | null>(null);
  const [installStep, setInstallStep] = useState<'idle' | 'verify' | 'sync' | 'done'>('idle');
  const [installedModelNames, setInstalledModelNames] = useState<string[]>([]);

  const { loadProviders } = useProvidersStore();
  const { isAuthenticated, bindToProject } = useStoreAuthStore();

  const fetchCategories = useCallback(async () => {
    const data = await storeApi.getModelCategories();
    return [
      { 
        id: 'all', 
        slug: 'all', 
        name_zh: t('tools.store.model.allModels'), 
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
  }, [t]);

  const {
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    loading,
    items: models,
    setItems: setModels,
    categories
  } = useStoreModal<ModelStoreItem, ModelStoreCategory>({
    isOpen,
    fetchItems: storeApi.getModels,
    fetchCategories,
    onUnauthorized: () => setShowLoginModal(true)
  });

  // Load installed models separately to sync status
  useEffect(() => {
    if (isOpen) {
      const loadInstalled = async () => {
        try {
          const installedNames = await storeApi.getInstalledModels();
          setInstalledModelNames(installedNames || []);
          
          // Update models list with installation status
          setModels(prev => prev.map(m => ({
            ...m,
            is_installed: installedNames.includes(m.name)
          })));
        } catch (error) {
          console.error('Failed to fetch installed models:', error);
        }
      };
      loadInstalled();
    }
  }, [isOpen, models.length > 0]); // Trigger when isOpen or when models are first loaded

  const handleModelClick = async (model: ModelStoreItem) => {
    setSelectedModel({
      ...model,
      is_installed: installedModelNames.includes(model.name)
    });
    setIsDetailOpen(true);
    
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

    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }

    setInstallingId(model.id);
    setInstallStep('verify');
    
    try {
      await bindToProject();
      setInstallStep('sync');

      if (model.is_installed) {
        await storeApi.uninstallModel(model.id);
      } else {
        await storeApi.installModel(model.id);
      }
      
      setInstallStep('done');
      
      const modelName = model.name;
      const newIsInstalled = !model.is_installed;

      setInstalledModelNames(prev => {
        if (model.is_installed) {
          return prev.filter(name => name !== modelName);
        } else {
          return [...prev, modelName];
        }
      });

      setModels(prev => prev.map(m => m.id === model.id ? { ...m, is_installed: newIsInstalled } : m));
      
      if (selectedModel?.id === model.id) {
        setSelectedModel(prev => prev ? { ...prev, is_installed: newIsInstalled } : null);
      }

      await loadProviders();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || error.message || t('common.saveFailed');
      showToast('error', t('common.error'), errorMsg);
    } finally {
      setInstallingId(null);
      setInstallStep('idle');
    }
  };

  return (
    <>
      <StoreModalBase isOpen={isOpen} onClose={onClose}
        sidebar={
          <StoreSidebar 
            title={t('tools.store.model.title', '模型商店')}
            icon={<Sparkles className="w-5 h-5" />}
            categories={categories}
            selectedCategory={selectedCategory}
            onCategoryChange={setSelectedCategory}
            themeColor="blue"
          />
        }
        header={
          <StoreHeader 
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            searchPlaceholder={t('tools.store.model.searchPlaceholder', '搜索模型...')}
            onClose={onClose}
            themeColor="blue"
            userStatus={
              <StoreUserStatus 
                themeColor="blue" 
                onLoginClick={() => setShowLoginModal(true)} 
              />
            }
          />
        }
      >
        <StoreContentArea 
          loading={loading} 
          isEmpty={!models || models.length === 0}
          themeColor="blue"
        >
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
        </StoreContentArea>
      </StoreModalBase>

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
    </>
  );
};

export default ModelStoreModal;
