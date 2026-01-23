import React, { useState, useEffect, useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { FiX, FiPlus, FiLoader, FiCheck, FiCpu } from 'react-icons/fi';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import { useProvidersStore, type ModelProviderConfig } from '@/stores/providersStore';
import { ToastContext } from '@/components/ui/ToastContainer';
import AIProvidersApiService from '@/services/aiProvidersApi';
import storeApi from '@/services/storeApi';

interface AddModelModalProps {
  isOpen: boolean;
  onClose: () => void;
  provider: ModelProviderConfig | null;
}

const AddModelModal: React.FC<AddModelModalProps> = ({ isOpen, onClose, provider }) => {
  const { t } = useTranslation();
  const toast = useContext(ToastContext);
  const { addModelToProvider, loadProviders } = useProvidersStore();

  const [loading, setLoading] = useState(false);
  const [remoteModels, setRemoteModels] = useState<any[]>([]);
  const [modelId, setModelId] = useState('');
  const [modelType, setModelType] = useState('chat');
  const [selectedModels, setSelectedModels] = useState<Array<{ id: string; type: string }>>([]);
  const [saving, setSaving] = useState(false);

  const isStore = provider?.isFromStore;

  useEffect(() => {
    if (isOpen && provider) {
      fetchAvailableModels();
    } else {
      setRemoteModels([]);
      setModelId('');
      setModelType('chat');
      setSelectedModels([]);
    }
  }, [isOpen, provider]);

  const fetchAvailableModels = async () => {
    if (!provider) return;
    setLoading(true);
    try {
      if (isStore && provider.storeResourceId) {
        // Store Mode
        const models = await storeApi.getModelsByProvider(provider.storeResourceId);
        // Mark installed status
        const currentModels = provider.models || [];
        setRemoteModels(models.map((m: any) => ({
          ...m,
          is_installed: currentModels.includes(m.name)
        })));
      } else {
        // Manual Mode - Try fetching list from provider using stored credentials
        const service = new AIProvidersApiService();
        const res = await service.getRemoteModels(provider.id);
        setRemoteModels(res.models || []);
      }
    } catch (e: any) {
      console.error('Failed to fetch models', e);
      // Don't show toast for manual mode as it might fail due to empty key
      if (isStore) {
        toast?.showToast('error', t('settings.providers.fetchModels.failed'), e?.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleInstallFromStore = async (model: any) => {
    setSaving(true);
    try {
      await storeApi.installModel(model.id);
      toast?.showToast('success', t('tools.store.model.installSuccess'));
      await loadProviders();
      onClose();
    } catch (e: any) {
      toast?.showToast('error', t('common.saveFailed'), e?.message);
    } finally {
      setSaving(false);
    }
  };

  const handleManualAdd = async () => {
    if (!provider || (selectedModels.length === 0 && !modelId.trim())) return;
    
    setSaving(true);
    try {
      const modelsToSubmit = [...selectedModels];
      if (modelId.trim() && !modelsToSubmit.some(m => m.id === modelId.trim())) {
        modelsToSubmit.push({ id: modelId.trim(), type: modelType });
      }

      await addModelToProvider(provider.id, modelsToSubmit.map(m => ({
        model_id: m.id,
        model_type: m.type
      })));
      toast?.showToast('success', t('settings.providers.toast.modelAdded'));
      onClose();
    } catch (e: any) {
      toast?.showToast('error', t('common.saveFailed'), e?.message);
    } finally {
      setSaving(false);
    }
  };

  const toggleModel = (id: string, type: string) => {
    setSelectedModels(prev => {
      const exists = prev.find(m => m.id === id);
      if (exists) {
        return prev.filter(m => m.id !== id);
      } else {
        return [...prev, { id, type }];
      }
    });
  };

  if (!isOpen || !provider) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 sm:p-6">
      <div className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm animate-in fade-in duration-300" onClick={onClose} />
      
      <div className="relative w-full max-w-md bg-white dark:bg-gray-900 rounded-[2rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 flex flex-col max-h-[80vh]">
        <header className="px-8 py-6 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <h2 className="text-xl font-black text-gray-900 dark:text-gray-100">
            {t('settings.providers.addModelTo')} {provider.name}
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-colors">
            <FiX className="w-5 h-5 text-gray-400" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar">
          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.modelType')}</label>
            <Select
              value={modelType}
              onChange={setModelType}
              options={[
                { value: 'chat', label: t('settings.providers.modelTypes.chat') },
                { value: 'embedding', label: t('settings.providers.modelTypes.embedding') },
              ]}
            />
          </div>

          {isStore ? (
            // Store Mode UI
            <div className="space-y-4">
              {loading ? (
                <div className="flex flex-col items-center justify-center py-10 gap-3 text-gray-500">
                  <FiLoader className="w-8 h-8 animate-spin" />
                  <p className="text-sm font-bold">{t('common.loading')}</p>
                </div>
              ) : remoteModels.filter(m => m.model_type === modelType).length === 0 ? (
                <div className="text-center py-10 text-gray-400">
                  <FiCpu className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p className="text-sm font-bold">{t('settings.providers.noStoreModels')}</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {remoteModels
                    .filter(m => m.model_type === modelType)
                    .map(m => (
                      <div 
                        key={m.id} 
                        className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-2xl border border-transparent hover:border-blue-200 dark:hover:border-blue-900 transition-all"
                      >
                        <div className="flex-1 min-w-0 mr-4">
                          <div className="font-black text-gray-900 dark:text-gray-100 truncate">{m.title_zh || m.name}</div>
                          <div className="text-[10px] text-gray-400 font-bold uppercase tracking-tighter">{m.name}</div>
                        </div>
                        {m.is_installed ? (
                          <div className="flex items-center gap-1 text-green-500 text-xs font-black uppercase">
                            <FiCheck />
                            {t('common.installed')}
                          </div>
                        ) : (
                          <Button 
                            size="sm" 
                            variant="primary" 
                            onClick={() => handleInstallFromStore(m)}
                            disabled={saving}
                            className="rounded-xl px-4 py-1.5 h-auto text-xs font-black"
                          >
                            {saving ? <FiLoader className="animate-spin mr-1" /> : <FiPlus className="mr-1" />}
                            {t('common.install')}
                          </Button>
                        )}
                      </div>
                    ))}
                </div>
              )}
            </div>
          ) : (
            // Manual Mode UI
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.modelId')} *</label>
                <div className="relative">
                  <div className="flex gap-2 mb-2 flex-wrap">
                    {selectedModels.map(m => (
                      <span key={m.id} className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-lg text-xs font-bold border border-blue-100 dark:border-blue-800">
                        {m.id}
                        <button onClick={() => toggleModel(m.id, m.type)} className="hover:text-red-500">
                          <FiX className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                  <input
                    className="w-full bg-gray-50 dark:bg-gray-800 border-none rounded-2xl px-4 py-3 text-sm font-bold focus:ring-2 focus:ring-blue-500 transition-all"
                    value={modelId}
                    onChange={(e) => setModelId(e.target.value)}
                    placeholder={t('settings.providers.placeholders.manualModelId')}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && modelId.trim()) {
                        toggleModel(modelId.trim(), modelType);
                        setModelId('');
                        e.preventDefault();
                      }
                    }}
                  />
                  
                  {loading ? (
                    <div className="mt-4 flex justify-center">
                      <FiLoader className="w-6 h-6 animate-spin text-blue-600" />
                    </div>
                  ) : remoteModels.length > 0 && (
                    <div className="mt-4 space-y-2">
                      <p className="px-1 text-[10px] font-black text-gray-400 uppercase tracking-widest">{t('settings.providers.suggestedModels')}</p>
                      <div className="grid grid-cols-1 gap-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                        {remoteModels
                          .filter(m => m.model_type === modelType)
                          .filter(m => !modelId.trim() || m.id.toLowerCase().includes(modelId.toLowerCase()))
                          .map(m => {
                            const isSelected = selectedModels.some(sm => sm.id === m.id);
                            return (
                              <button
                                key={m.id}
                                onClick={() => toggleModel(m.id, m.model_type || modelType)}
                                className={`w-full text-left px-4 py-3 rounded-2xl text-sm font-bold transition-all flex justify-between items-center ${
                                  isSelected 
                                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-100 dark:shadow-none' 
                                    : 'bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-white dark:hover:bg-gray-700'
                                }`}
                              >
                                <span>{m.id}</span>
                                {isSelected && <FiCheck className="w-4 h-4" />}
                              </button>
                            );
                          })}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-4">
                <Button 
                  variant="primary" 
                  className="w-full py-4 rounded-2xl font-black shadow-xl shadow-blue-200 dark:shadow-none"
                  onClick={handleManualAdd}
                  disabled={saving || (selectedModels.length === 0 && !modelId.trim())}
                >
                  {saving ? <FiLoader className="animate-spin mr-2" /> : <FiPlus className="mr-2" />}
                  {selectedModels.length > 0 ? `${t('common.add')} (${selectedModels.length})` : t('common.add')}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AddModelModal;
