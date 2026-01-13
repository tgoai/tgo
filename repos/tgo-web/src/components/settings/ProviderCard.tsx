import React from 'react';
import { useTranslation } from 'react-i18next';
import { FiEdit2, FiTrash2, FiLoader, FiZap, FiBox, FiCheckCircle } from 'react-icons/fi';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { type ModelProviderConfig } from '@/stores/providersStore';

interface ProviderCardProps {
  provider: ModelProviderConfig;
  onEdit: (provider: ModelProviderConfig) => void;
  onDelete: (id: string) => void;
  onTest: (provider: ModelProviderConfig) => void;
  isTesting: boolean;
}

const ProviderCard: React.FC<ProviderCardProps> = ({ 
  provider, 
  onEdit, 
  onDelete, 
  onTest,
  isTesting 
}) => {
  const { t } = useTranslation();
  const isStore = provider.name.startsWith('Store-');
  const displayName = isStore ? provider.name.replace('Store-', '') : provider.name;

  return (
    <div className="group relative bg-white dark:bg-gray-900 rounded-[2rem] border border-gray-100 dark:border-gray-800 p-8 hover:shadow-2xl hover:shadow-blue-500/10 hover:-translate-y-1 transition-all duration-500 overflow-hidden">
      {/* Background Glow */}
      <div className={`absolute -top-24 -right-24 w-48 h-48 blur-3xl transition-all duration-500 rounded-full ${isStore ? 'bg-purple-500/5 group-hover:bg-purple-500/10' : 'bg-blue-500/5 group-hover:bg-blue-500/10'}`} />
      
      <div className="relative z-10">
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center gap-4">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-white shadow-xl ${isStore ? 'bg-purple-600 shadow-purple-200 dark:shadow-none' : 'bg-blue-600 shadow-blue-200 dark:shadow-none'}`}>
              {isStore ? <FiBox className="w-7 h-7" /> : <FiZap className="w-7 h-7" />}
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="text-xl font-black text-gray-900 dark:text-gray-100 tracking-tight">
                  {displayName}
                </h3>
                {provider.enabled && (
                  <Badge variant="success" size="sm">
                    <div className="flex items-center gap-1">
                      <FiCheckCircle className="w-3 h-3" />
                      {t('common.enabled')}
                    </div>
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs font-bold text-gray-400 uppercase tracking-widest">
                {isStore ? (
                  <span className="text-purple-500">{t('settings.providers.storeModel')}</span>
                ) : (
                  <span>{provider.kind}</span>
                )}
                <span className="text-gray-200 dark:text-gray-700">•</span>
                <span className="truncate max-w-[200px]">{provider.apiBaseUrl || 'Default URL'}</span>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4 mb-8">
          <div className="flex flex-wrap gap-1.5">
            {(provider.models || []).slice(0, 5).map((m) => (
              <span key={m} className={`px-3 py-1 text-[10px] font-black rounded-lg border uppercase tracking-tighter ${provider.defaultModel === m ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700' : 'bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 border-gray-100 dark:border-gray-700'}`}>
                {m}{provider.defaultModel === m ? ` (${t('settings.providers.badges.default')})` : ''}
              </span>
            ))}
            {(provider.models?.length || 0) > 5 && (
              <span className="px-3 py-1 text-[10px] font-black bg-gray-50 dark:bg-gray-800 text-gray-400 rounded-lg border border-gray-100 dark:border-gray-700">
                +{(provider.models?.length || 0) - 5} {t('common.more').toUpperCase()}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between pt-6 border-t border-gray-50 dark:border-gray-800">
          <div className="flex gap-2">
            {!isStore && (
              <>
                <Button 
                  variant="secondary" 
                  size="sm" 
                  onClick={() => onTest(provider)} 
                  disabled={isTesting}
                  className="rounded-xl font-bold"
                >
                  {isTesting ? <FiLoader className="animate-spin mr-1" /> : null}
                  {t('settings.providers.testButton', '测试')}
                </Button>
                <Button 
                  variant="secondary" 
                  size="sm" 
                  onClick={() => onEdit(provider)}
                  className="rounded-xl font-bold"
                >
                  <FiEdit2 className="mr-1" />
                  {t('common.edit', '编辑')}
                </Button>
              </>
            )}
          </div>
          
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => onDelete(provider.id)}
            className="text-red-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-xl font-bold"
          >
            <FiTrash2 className="mr-1" />
            {t('common.delete', '删除')}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ProviderCard;
