import React, { useState, useEffect, useRef, useMemo, useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { FiEye, FiEyeOff, FiLoader, FiChevronDown, FiChevronUp, FiX, FiCheck, FiPlus } from 'react-icons/fi';
import Button from '@/components/ui/Button';
import Select from '@/components/ui/Select';
import { useProvidersStore, type ModelProviderConfig, type ProviderKind } from '@/stores/providersStore';
import { ToastContext } from '@/components/ui/ToastContainer';
import AIProvidersApiService from '@/services/aiProvidersApi';

interface ProviderConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  editingProvider: ModelProviderConfig | null;
}

type Draft = Omit<ModelProviderConfig, 'id' | 'createdAt' | 'updatedAt'> & { id?: string };

const emptyDraft = (t: (k: string, d: string) => string): Draft => ({
  kind: 'openai',
  name: t('settings.providers.defaultName', '新提供商'),
  apiKey: '',
  apiBaseUrl: 'https://api.openai.com/v1',
  models: [],
  defaultModel: '',
  enabled: true,
  params: { azure: { apiVersion: '2024-02-15-preview' } },
});

const ProviderConfigModal: React.FC<ProviderConfigModalProps> = ({ isOpen, onClose, editingProvider }) => {
  const { t } = useTranslation();
  const toast = useContext(ToastContext);
  const { addProvider, updateProvider } = useProvidersStore();

  const [draft, setDraft] = useState<Draft | null>(null);
  const [revealKey, setRevealKey] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsQuery, setModelsQuery] = useState('');
  const [modelOptions, setModelOptions] = useState<Array<{ id: string; name?: string }>>([]);
  const [isModelsOpen, setIsModelsOpen] = useState(false);
  const modelsBoxRef = useRef<HTMLDivElement | null>(null);

  const providerOptions: Array<{ value: ProviderKind; label: string; hint?: string }> = useMemo(() => [
    { value: 'openai', label: t('settings.providers.provider.openai', 'OpenAI'), hint: 'https://api.openai.com/v1' },
    { value: 'azure', label: t('settings.providers.provider.azure', 'Azure OpenAI'), hint: 'https://{resource}.openai.azure.com' },
    { value: 'qwen', label: t('settings.providers.provider.qwen', '通义千问 (DashScope)'), hint: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
    { value: 'moonshot', label: t('settings.providers.provider.moonshot', '月之暗面 (Kimi)'), hint: 'https://api.moonshot.cn/v1' },
    { value: 'deepseek', label: t('settings.providers.provider.deepseek', 'DeepSeek'), hint: 'https://api.deepseek.com/v1' },
    { value: 'ollama', label: t('settings.providers.provider.ollama', 'Ollama'), hint: 'http://localhost:11434' },
    { value: 'custom', label: t('settings.providers.provider.custom', '自定义'), hint: t('settings.providers.placeholders.baseUrl.custom', '自定义 Base URL') },
  ], [t]);

  useEffect(() => {
    if (isOpen) {
      if (editingProvider) {
        setDraft({ ...editingProvider });
      } else {
        setDraft(emptyDraft(t));
      }
      setIsAdvancedOpen(false);
      setRevealKey(false);
    } else {
      setDraft(null);
    }
  }, [isOpen, editingProvider, t]);

  useEffect(() => {
    if (!isModelsOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (modelsBoxRef.current && !modelsBoxRef.current.contains(e.target as Node)) {
        setIsModelsOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [isModelsOpen]);

  const providerLabel = (kind: ProviderKind) => providerOptions.find(o => o.value === kind)?.label || kind;

  const fetchModelOptions = async () => {
    if (!draft) return;
    try {
      setModelsLoading(true);
      const service = new AIProvidersApiService();
      const providerKey = AIProvidersApiService.kindToProviderKey(draft.kind);
      
      const requestBody: any = { provider: providerKey };
      if (draft.apiKey?.trim()) requestBody.api_key = draft.apiKey.trim();
      if (draft.apiBaseUrl?.trim()) requestBody.api_base_url = draft.apiBaseUrl.trim();
      
      if (draft.kind === 'azure' && draft.params?.azure) {
        requestBody.config = {
          deployment: draft.params.azure.deployment,
          resource: draft.params.azure.resource,
          api_version: draft.params.azure.apiVersion,
        };
      }
      
      const res = await service.listModels(requestBody);
      const opts = (res.models || []).map((m: any) => ({ id: m.id, name: m.name })).filter((o: any) => o.id);
      setModelOptions(opts);
    } catch (e: any) {
      toast?.showToast('error', t('settings.providers.fetchModels.failed', '获取模型失败'), e?.message);
    } finally {
      setModelsLoading(false);
    }
  };

  const handleTest = async () => {
    if (!draft) return;
    setTesting(true);
    try {
      const service = new AIProvidersApiService();
      // If it's a new provider, we might need a temporary test or just save first
      // But for now, let's assume we can test with existing ID or by passing config
      if (draft.id) {
        const res = await service.testProvider(draft.id);
        if ((res as any).ok ?? (res as any).success ?? true) {
          toast?.showToast('success', t('settings.providers.test.ok', '连接成功'));
        } else {
          toast?.showToast('error', t('settings.providers.test.failed', '连接失败'));
        }
      } else {
        // For new providers, we'd need a backend endpoint that tests a config DTO
        // For now, let's show a message that they should save first or just skip
        toast?.showToast('info', t('settings.providers.test.saveFirst', '请先保存后再测试'));
      }
    } catch (err: any) {
      toast?.showToast('error', t('settings.providers.test.failed', '连接失败'), err?.message);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!draft) return;
    if (!draft.apiKey?.trim() && !draft.id) {
      toast?.showToast('warning', t('settings.providers.validate.apiKey', '请输入 API Key'));
      return;
    }
    setSaving(true);
    try {
      const models = (draft.models || []).map(m => m.trim()).filter(Boolean);
      const defaultModel = draft.defaultModel && models.includes(draft.defaultModel.trim())
        ? draft.defaultModel.trim()
        : (models[0] || '');

      const data = {
        kind: draft.kind,
        name: draft.name?.trim() || providerLabel(draft.kind),
        apiKey: draft.apiKey.trim(),
        apiBaseUrl: draft.apiBaseUrl?.trim(),
        models,
        defaultModel,
        enabled: !!draft.enabled,
        params: draft.params,
      };

      if (draft.id) {
        await updateProvider(draft.id, data);
        toast?.showToast('success', t('settings.providers.toast.saved', '已保存修改'));
      } else {
        await addProvider(data);
        toast?.showToast('success', t('settings.providers.toast.added', '已添加提供商'));
      }
      onClose();
    } catch (e: any) {
      toast?.showToast('error', t('common.saveFailed', '保存失败'), e?.message);
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen || !draft) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div className="absolute inset-0 bg-gray-900/60 backdrop-blur-sm animate-in fade-in duration-300" onClick={onClose} />
      
      <div className="relative w-full max-w-lg bg-white dark:bg-gray-900 rounded-[2rem] shadow-2xl overflow-hidden animate-in zoom-in-95 duration-300 flex flex-col max-h-[90vh]">
        <header className="px-8 py-6 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <h2 className="text-xl font-black text-gray-900 dark:text-gray-100">
            {editingProvider ? t('settings.providers.edit', '编辑提供商') : t('settings.providers.add', '添加提供商')}
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-colors">
            <FiX className="w-5 h-5 text-gray-400" />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto p-8 space-y-6 custom-scrollbar">
          {/* Provider Kind */}
          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.kind', '提供商类型')} *</label>
            <Select
              value={draft.kind}
              onChange={(val) => {
                const kind = val as ProviderKind;
                const opt = providerOptions.find(o => o.value === kind);
                setDraft({
                  ...draft,
                  kind,
                  apiBaseUrl: opt?.hint || '',
                  name: draft.name === providerLabel(draft.kind) ? providerLabel(kind) : draft.name
                });
              }}
              options={providerOptions.map(o => ({ value: o.value, label: o.label }))}
            />
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.apiKey', 'API Key')} *</label>
            <div className="relative">
              <input
                type={revealKey ? 'text' : 'password'}
                className="w-full bg-gray-50 dark:bg-gray-800 border-none rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 transition-all pr-12"
                value={draft.apiKey}
                onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                placeholder={draft.apiKeyMasked ? t('settings.providers.placeholders.apiKeyMasked', `已配置：${draft.apiKeyMasked}`) : t('settings.providers.placeholders.apiKey', '输入密钥')}
              />
              <button
                type="button"
                onClick={() => setRevealKey(!revealKey)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {revealKey ? <FiEyeOff /> : <FiEye />}
              </button>
            </div>
          </div>

          {/* Advanced Options Toggle */}
          <button
            onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
            className="flex items-center gap-2 text-sm font-bold text-blue-600 hover:text-blue-700 transition-colors"
          >
            {isAdvancedOpen ? <FiChevronUp /> : <FiChevronDown />}
            {t('common.advancedOptions')}
          </button>

          {isAdvancedOpen && (
            <div className="space-y-6 pt-2 animate-in slide-in-from-top-2 duration-300">
              {/* Name / Alias */}
              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.name')}</label>
                <input
                  className="w-full bg-gray-50 dark:bg-gray-800 border-none rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 transition-all"
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  placeholder={providerLabel(draft.kind)}
                />
              </div>

              {/* Base URL */}
              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.baseUrl')}</label>
                <input
                  className="w-full bg-gray-50 dark:bg-gray-800 border-none rounded-2xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 transition-all"
                  value={draft.apiBaseUrl || ''}
                  onChange={(e) => setDraft({ ...draft, apiBaseUrl: e.target.value })}
                  placeholder="https://..."
                />
              </div>

              {/* Azure Config */}
              {draft.kind === 'azure' && (
                <div className="grid grid-cols-1 gap-4 p-4 bg-blue-50/50 dark:bg-blue-900/10 rounded-2xl border border-blue-100 dark:border-blue-900/30">
                  <div className="space-y-1">
                    <label className="text-xs font-black text-blue-600 dark:text-blue-400 uppercase">{t('settings.providers.fields.azure.deployment')}</label>
                    <input
                      className="w-full bg-white dark:bg-gray-800 border-none rounded-xl px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                      value={draft.params?.azure?.deployment || ''}
                      onChange={(e) => setDraft({ ...draft, params: { ...draft.params, azure: { ...(draft.params?.azure || {}), deployment: e.target.value } } })}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-xs font-black text-blue-600 dark:text-blue-400 uppercase">{t('settings.providers.fields.azure.resource')}</label>
                      <input
                        className="w-full bg-white dark:bg-gray-800 border-none rounded-xl px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                        value={draft.params?.azure?.resource || ''}
                        onChange={(e) => setDraft({ ...draft, params: { ...draft.params, azure: { ...(draft.params?.azure || {}), resource: e.target.value } } })}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-black text-blue-600 dark:text-blue-400 uppercase">{t('settings.providers.fields.azure.apiVersion')}</label>
                      <input
                        className="w-full bg-white dark:bg-gray-800 border-none rounded-xl px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
                        value={draft.params?.azure?.apiVersion || ''}
                        onChange={(e) => setDraft({ ...draft, params: { ...draft.params, azure: { ...(draft.params?.azure || {}), apiVersion: e.target.value } } })}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Models List */}
              <div className="space-y-2">
                <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.models')}</label>
                <div className="relative" ref={modelsBoxRef}>
                  <div
                    className="flex flex-wrap items-center gap-2 bg-gray-50 dark:bg-gray-800 rounded-2xl p-2 min-h-[3rem] cursor-text focus-within:ring-2 focus-within:ring-blue-500 transition-all"
                    onClick={() => { setIsModelsOpen(true); if (modelOptions.length === 0) fetchModelOptions(); }}
                  >
                    {(draft.models || []).map((m, idx) => (
                      <span key={`${m}-${idx}`} className="inline-flex items-center gap-1 px-3 py-1 bg-white dark:bg-gray-700 rounded-xl text-xs font-bold text-gray-700 dark:text-gray-200 shadow-sm border border-gray-100 dark:border-gray-600">
                        {m}
                        <button onClick={(e) => { e.stopPropagation(); setDraft({ ...draft, models: draft.models?.filter(x => x !== m) }); }} className="text-gray-400 hover:text-red-500">
                          <FiX />
                        </button>
                      </span>
                    ))}
                    <input
                      className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-1 min-w-[100px]"
                      value={modelsQuery}
                      onChange={(e) => setModelsQuery(e.target.value)}
                      onFocus={() => { setIsModelsOpen(true); if (modelOptions.length === 0) fetchModelOptions(); }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && modelsQuery.trim()) {
                          const val = modelsQuery.trim();
                          if (!draft.models?.includes(val)) {
                            setDraft({ ...draft, models: [...(draft.models || []), val] });
                          }
                          setModelsQuery('');
                          e.preventDefault();
                        }
                      }}
                      placeholder={t('settings.providers.placeholders.modelsSearch')}
                    />
                  </div>

                  {isModelsOpen && (
                    <div className="absolute z-50 mt-2 w-full bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                      <div className="p-2 max-h-60 overflow-y-auto custom-scrollbar">
                        {modelsLoading ? (
                          <div className="flex items-center justify-center p-4 gap-2 text-sm text-gray-500">
                            <FiLoader className="animate-spin" />
                            {t('common.loading', '加载中...')}
                          </div>
                        ) : (
                          <>
                            {modelsQuery.trim() && !modelOptions.some(o => o.id === modelsQuery.trim()) && (
                              <button
                                onClick={() => {
                                  if (!draft.models?.includes(modelsQuery.trim())) {
                                    setDraft({ ...draft, models: [...(draft.models || []), modelsQuery.trim()] });
                                  }
                                  setModelsQuery('');
                                  setIsModelsOpen(false);
                                }}
                                className="w-full flex items-center gap-2 px-4 py-3 hover:bg-blue-50 dark:hover:bg-blue-900/20 text-sm font-bold text-blue-600 rounded-xl transition-colors"
                              >
                                <FiPlus />
                                {t('settings.providers.createModelOption', '创建')} "{modelsQuery.trim()}"
                              </button>
                            )}
                            {modelOptions.filter(o => o.id.toLowerCase().includes(modelsQuery.toLowerCase())).map(opt => (
                              <button
                                key={opt.id}
                                onClick={() => {
                                  const exists = draft.models?.includes(opt.id);
                                  setDraft({
                                    ...draft,
                                    models: exists ? draft.models?.filter(m => m !== opt.id) : [...(draft.models || []), opt.id]
                                  });
                                }}
                                className={`w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-700/50 text-sm rounded-xl transition-colors ${draft.models?.includes(opt.id) ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600' : 'text-gray-700 dark:text-gray-300'}`}
                              >
                                <div className="text-left">
                                  <div className="font-bold">{opt.id}</div>
                                  {opt.name && <div className="text-xs opacity-50">{opt.name}</div>}
                                </div>
                                {draft.models?.includes(opt.id) && <FiCheck className="w-4 h-4" />}
                              </button>
                            ))}
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

          {/* Default Model */}
          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700 dark:text-gray-300">{t('settings.providers.fields.defaultModel')}</label>
            <Select
              value={draft.defaultModel || ''}
              onChange={(val) => setDraft({ ...draft, defaultModel: val })}
              options={(draft.models || []).map(m => ({ value: m, label: m }))}
              disabled={!draft.models?.length}
              placeholder={t('settings.providers.selectDefaultModel')}
            />
          </div>
        </div>
      )}
    </div>

    <footer className="px-8 py-6 bg-gray-50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-800 flex items-center justify-between gap-4">
      <div className="flex gap-3">
        <Button variant="secondary" size="md" onClick={onClose}>{t('common.cancel')}</Button>
        <Button variant="secondary" size="md" onClick={handleTest} disabled={testing}>
          {testing ? <FiLoader className="animate-spin mr-2" /> : null}
          {t('settings.providers.testButton')}
        </Button>
      </div>
      <Button variant="primary" size="md" onClick={handleSave} disabled={saving}>
        {saving ? <FiLoader className="animate-spin mr-2" /> : null}
        {t('common.save')}
      </Button>
    </footer>
      </div>
    </div>
  );
};

export default ProviderConfigModal;
