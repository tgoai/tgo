import React, { useState, useMemo, useCallback } from 'react';
import { Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ToolStoreCard from './ToolStoreCard';
import ToolStoreDetail from './ToolStoreDetail';
import StoreLoginModal from './StoreLoginModal';
import { storeApi } from '@/services/storeApi';
import { useProjectToolsStore } from '@/stores/projectToolsStore';
import { useStoreAuthStore } from '@/stores/storeAuthStore';
import { useToast } from './ToolToastProvider';
import type { ToolStoreItem, ToolStoreCategory } from '@/types';

// New Base Components and Hook
import { 
  StoreModalBase, 
  StoreSidebar, 
  StoreHeader, 
  StoreUserStatus, 
  StoreContentArea 
} from './store';
import { useStoreModal } from './store/hooks/useStoreModal';

interface ToolStoreModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const ToolStoreModal: React.FC<ToolStoreModalProps> = ({ isOpen, onClose }) => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  
  const [selectedTool, setSelectedTool] = useState<ToolStoreItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [installingId, setInstallingId] = useState<string | null>(null);

  const { aiTools, loadTools } = useProjectToolsStore();
  const { isAuthenticated, bindToProject } = useStoreAuthStore();

  const fetchCategories = useCallback(async () => {
    const data = await storeApi.getToolCategories();
    return [
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
  }, []);

  const {
    searchQuery,
    setSearchQuery,
    selectedCategory,
    setSelectedCategory,
    loading,
    items: tools,
    categories
  } = useStoreModal<ToolStoreItem, ToolStoreCategory>({
    isOpen,
    fetchItems: storeApi.getTools,
    fetchCategories,
    onUnauthorized: () => setShowLoginModal(true)
  });

  // Check if a tool is already installed in the project
  const installedToolNames = useMemo(() => {
    return new Set(aiTools.map(t => t.name.toLowerCase()));
  }, [aiTools]);

  const handleToolClick = async (tool: ToolStoreItem) => {
    setSelectedTool(tool);
    setIsDetailOpen(true);
    
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
      await bindToProject();
      await storeApi.installTool(tool.id);
      await loadTools(false);
    } catch (error) {
      showToast('error', t('common.error', '错误'), t('common.saveFailed', '保存失败'));
    } finally {
      setInstallingId(null);
    }
  };

  return (
    <>
      <StoreModalBase isOpen={isOpen} onClose={onClose}
        sidebar={
          <StoreSidebar 
            title={t('tools.toolStore', '工具商店')}
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
            searchPlaceholder={t('tools.store.searchPlaceholder', '搜索工具、作者或标签...')}
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
          isEmpty={!tools || tools.length === 0}
          themeColor="blue"
        >
          {tools.map(tool => (
            <ToolStoreCard 
              key={tool.id} 
              tool={tool} 
              onClick={handleToolClick}
              onInstall={handleInstall}
              isInstalled={installedToolNames.has(tool.name.toLowerCase())}
            />
          ))}
        </StoreContentArea>
      </StoreModalBase>

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
    </>
  );
};

export default ToolStoreModal;
