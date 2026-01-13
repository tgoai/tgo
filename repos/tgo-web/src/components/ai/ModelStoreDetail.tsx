import React from 'react';
import { X, Brain, Zap, ShieldCheck, Globe, Check, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { ModelStoreItem } from '@/types';

interface ModelStoreDetailProps {
  model: ModelStoreItem | null;
  isOpen: boolean;
  onClose: () => void;
  onInstall: (model: ModelStoreItem) => void;
  isInstalled: boolean;
  installingId: string | null;
  installStep: 'idle' | 'verify' | 'sync' | 'done';
}

const ModelStoreDetail: React.FC<ModelStoreDetailProps> = ({
  model,
  isOpen,
  onClose,
  onInstall,
  isInstalled,
  installingId,
  installStep
}) => {
  const { t } = useTranslation();
  if (!model) return null;

  const isInstalling = installingId === model.id;

  return (
    <div className={`fixed inset-y-0 right-0 w-full sm:w-[500px] md:w-[600px] bg-white dark:bg-gray-950 shadow-2xl z-[60] transform transition-transform duration-500 ease-out flex flex-col border-l border-gray-100 dark:border-gray-800 ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
      {/* Header */}
      <header className="p-8 flex items-center justify-between border-b border-gray-50 dark:border-gray-900 bg-white/50 dark:bg-gray-950/50 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-blue-600 flex items-center justify-center text-white shadow-lg">
            <Brain className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-black text-gray-900 dark:text-gray-100 tracking-tight">
              {t('tools.store.model.details')}
            </h2>
          </div>
        </div>
        <button 
          onClick={onClose}
          className="p-3 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-2xl text-gray-500 transition-all active:scale-90"
        >
          <X className="w-5 h-5" />
        </button>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-10 space-y-12">
        {/* Main Info */}
        <section className="space-y-6">
          <div className="flex flex-wrap items-center gap-3">
            <span className="px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg text-[10px] font-black uppercase tracking-widest">
              {model.model_type}
            </span>
            <span className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 text-gray-500 rounded-lg text-[10px] font-black uppercase tracking-widest flex items-center gap-2">
              <Globe className="w-3 h-3" />
              {model.provider?.name || t('common.unknown')}
            </span>
            {isInstalled && (
              <span className="px-3 py-1.5 bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 rounded-lg text-[10px] font-black uppercase tracking-widest flex items-center gap-1">
                <Check className="w-3 h-3" />
                {t('tools.store.model.installed')}
              </span>
            )}
          </div>

          <h1 className="text-4xl font-black text-gray-900 dark:text-gray-100 tracking-tight leading-tight">
            {model.title_zh || model.name}
          </h1>

          <div className="flex items-center gap-2 text-blue-600 font-bold text-sm">
            <ShieldCheck className="w-5 h-5" />
            {t('tools.store.verified')}
          </div>
        </section>

        {/* Pricing */}
        <section className="grid grid-cols-2 gap-6">
          <div className="p-8 bg-gray-50 dark:bg-gray-900 rounded-[2rem] border border-gray-100 dark:border-gray-800">
            <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">
              {t('tools.store.model.priceInput')}
            </p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-black text-gray-900 dark:text-gray-100">${Number(model.input_price).toFixed(2)}</span>
              <span className="text-xs font-bold text-gray-400">/{t('tools.store.model.perMillionTokens')}</span>
            </div>
          </div>
          <div className="p-8 bg-gray-50 dark:bg-gray-900 rounded-[2rem] border border-gray-100 dark:border-gray-800">
            <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-3">
              {t('tools.store.model.priceOutput')}
            </p>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-black text-gray-900 dark:text-gray-100">${Number(model.output_price).toFixed(2)}</span>
              <span className="text-xs font-bold text-gray-400">/{t('tools.store.model.perMillionTokens')}</span>
            </div>
          </div>
        </section>

        {/* Capabilities */}
        <section className="space-y-6">
          <h3 className="text-lg font-black text-gray-900 dark:text-gray-100 uppercase tracking-tight flex items-center gap-2">
            <Zap className="w-5 h-5 text-blue-600" />
            {t('tools.store.model.capabilities')}
          </h3>
          <div className="grid grid-cols-1 gap-4">
            <div className="p-6 bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <span className="text-sm font-bold text-gray-500">{t('tools.store.model.contextWindow')}</span>
              <span className="text-sm font-black text-gray-900 dark:text-gray-100">
                {model.context_window ? `${Math.round(model.context_window / 1024)}k Tokens` : t('common.unknown')}
              </span>
            </div>
            <div className="p-6 bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 flex items-center justify-between">
              <span className="text-sm font-bold text-gray-500">{t('tools.store.model.type')}</span>
              <span className="text-sm font-black text-gray-900 dark:text-gray-100 uppercase tracking-wider">
                {model.model_type}
              </span>
            </div>
          </div>
        </section>

        {/* Description */}
        <section className="space-y-6">
          <h3 className="text-lg font-black text-gray-900 dark:text-gray-100 uppercase tracking-tight">
            {t('tools.store.model.details')}
          </h3>
          <div className="prose prose-blue dark:prose-invert max-w-none">
            <p className="text-gray-500 dark:text-gray-400 text-lg leading-relaxed font-medium">
              {model.description_zh || model.description_en}
            </p>
            {model.description_zh && model.description_en && (
              <p className="text-gray-400 dark:text-gray-500 italic mt-6 border-t border-gray-50 dark:border-gray-900 pt-6">
                {model.description_en}
              </p>
            )}
          </div>
        </section>
      </div>

      {/* Footer / Actions */}
      <footer className="p-8 border-t border-gray-50 dark:border-gray-900 bg-gray-50/50 dark:bg-gray-950/50 backdrop-blur-xl">
        {isInstalled ? (
          <div className="flex flex-col gap-4">
            <div className="flex items-center justify-center gap-2 text-green-600 font-bold py-4 bg-green-50 dark:bg-green-900/20 rounded-2xl">
              <Check className="w-5 h-5" />
              {t('tools.store.model.installed')}
            </div>
            <button
              onClick={() => onInstall(model)}
              disabled={isInstalling}
              className="w-full py-5 bg-white dark:bg-gray-900 border border-red-100 dark:border-red-900/30 text-red-500 font-black rounded-2xl hover:bg-red-50 dark:hover:bg-red-900/20 transition-all active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {isInstalling ? (
                <>
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="text-xs uppercase tracking-widest">{t(`tools.store.model.installStep.${installStep}`)}</span>
                </>
              ) : t('tools.store.model.stopUsing')}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <button
              onClick={() => onInstall(model)}
              disabled={isInstalling}
              className="w-full py-5 bg-blue-600 hover:bg-blue-700 text-white font-black rounded-2xl shadow-xl shadow-blue-200 dark:shadow-none transition-all active:scale-[0.98] flex items-center justify-center gap-2 group disabled:opacity-50"
            >
              {isInstalling ? (
                <>
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="text-xs uppercase tracking-widest">{t(`tools.store.model.installStep.${installStep}`)}</span>
                </>
              ) : (
                <>
                  <Zap className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  {t('tools.store.model.startUsing')}
                </>
              )}
            </button>
            <p className="text-[10px] text-gray-400 text-center font-bold uppercase tracking-widest leading-relaxed px-8">
              {t('tools.store.model.usageNotice')}
            </p>
          </div>
        )}
      </footer>
    </div>
  );
};

export default ModelStoreDetail;
