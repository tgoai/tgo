import React from 'react';
import { Brain, Zap, ShieldCheck, Check, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { ModelStoreItem } from '@/types';

interface ModelStoreCardProps {
  model: ModelStoreItem;
  onClick: (model: ModelStoreItem) => void;
  onInstall: (e: React.MouseEvent, model: ModelStoreItem) => void;
  isInstalled: boolean;
  installingId: string | null;
  installStep: 'idle' | 'verify' | 'sync' | 'done';
}

const ModelStoreCard: React.FC<ModelStoreCardProps> = ({ 
  model, 
  onClick, 
  onInstall,
  isInstalled,
  installingId,
  installStep
}) => {
  const { t } = useTranslation();
  const isInstalling = installingId === model.id;

  return (
    <div 
      onClick={() => onClick(model)}
      className="group relative bg-white dark:bg-gray-900 rounded-[2rem] border border-gray-100 dark:border-gray-800 p-8 hover:shadow-2xl hover:shadow-blue-500/10 hover:-translate-y-1 transition-all duration-500 cursor-pointer overflow-hidden"
    >
      {/* Background Glow */}
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-blue-500/5 blur-3xl group-hover:bg-blue-500/10 transition-all duration-500 rounded-full" />
      
      <div className="relative z-10">
        <div className="flex items-start justify-between mb-6">
          <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center text-white shadow-xl shadow-blue-200 dark:shadow-none">
            <Brain className="w-8 h-8" />
          </div>
          {isInstalled && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 rounded-full text-[10px] font-black uppercase tracking-widest animate-in fade-in zoom-in duration-300">
              <Check className="w-3 h-3" />
              {t('tools.store.model.installed')}
            </div>
          )}
        </div>

        <div className="space-y-2 mb-6">
          <div className="flex items-center gap-2">
            <h3 className="text-xl font-black text-gray-900 dark:text-gray-100 tracking-tight truncate group-hover:text-blue-600 transition-colors">
              {model.title_zh || model.name}
            </h3>
            <ShieldCheck className="w-4 h-4 text-blue-500 flex-shrink-0" />
          </div>
          <p className="text-xs font-bold text-gray-400 uppercase tracking-widest">
            {model.provider?.name || t('common.unknown')}
          </p>
        </div>

        <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 font-medium leading-relaxed mb-8 h-10">
          {model.description_zh || model.description_en}
        </p>

        <div className="flex items-center justify-between pt-6 border-t border-gray-50 dark:border-gray-800">
          <div className="space-y-1">
            <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest">
              {t('tools.store.model.priceInput')}
            </p>
            <p className="text-lg font-black text-gray-900 dark:text-gray-100">
              ${Number(model.input_price).toFixed(2)}
              <span className="text-[10px] text-gray-400 ml-1">/1M</span>
            </p>
          </div>

          <button
            onClick={(e) => !isInstalling && onInstall(e, model)}
            disabled={isInstalling}
            className={`relative flex items-center justify-center w-12 h-12 rounded-2xl transition-all active:scale-90 ${
              isInstalling
                ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600'
                : isInstalled 
                  ? 'bg-green-50 dark:bg-green-900/20 text-green-600' 
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-400 hover:bg-blue-600 hover:text-white'
            }`}
          >
            {isInstalling ? (
              <div className="flex flex-col items-center">
                <Loader2 className="w-5 h-5 animate-spin" />
                <span className="absolute -bottom-5 text-[8px] font-black whitespace-nowrap text-blue-500 uppercase tracking-tighter">
                  {t(`tools.store.model.installStep.${installStep}`)}
                </span>
              </div>
            ) : (
              <Zap className={`w-5 h-5 ${isInstalled ? 'fill-current' : ''}`} />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ModelStoreCard;
