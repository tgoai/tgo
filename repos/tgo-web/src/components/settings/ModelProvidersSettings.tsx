import React, { useMemo, useState, useContext, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { FiCpu, FiPlus, FiEdit2, FiTrash2, FiEye, FiEyeOff, FiLoader, FiHelpCircle } from 'react-icons/fi';
import Button from '@/components/ui/Button';
import Toggle from '@/components/ui/Toggle';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import SectionCard from '@/components/ui/SectionCard';
import SectionHeader from '@/components/ui/SectionHeader';

import { useProvidersStore, type ModelProviderConfig, type ProviderKind } from '@/stores/providersStore';
import { ToastContext } from '@/components/ui/ToastContainer';
import AIProvidersApiService from '@/services/aiProvidersApi';
import ProjectConfigApiService from '@/services/projectConfigApi';
import { useAuthStore } from '@/stores/authStore';
import UIBadge from '@/components/ui/Badge';


import { useAppSettingsStore } from '@/stores/appSettingsStore';
// Provider options will be constructed inside the component with i18n labels/hints to avoid hardcoded text.

type Draft = Omit<ModelProviderConfig, 'id' | 'createdAt' | 'updatedAt'> & { id?: string };

const emptyDraft = (t: (k: string, d: string)=>string): Draft => ({
  kind: 'openai',
  name: t('settings.providers.defaultName', '新提供商'),
  apiKey: '',
  apiBaseUrl: 'https://api.openai.com/v1',
  models: [],
  defaultModel: '',
  enabled: true,
  params: { azure: { apiVersion: '2024-02-15-preview' } }
});


const FieldRow: React.FC<{ label: string; required?: boolean; children: React.ReactNode }>
  = ({ label, required, children }) => (
  <div className="grid grid-cols-12 items-center gap-3 py-2">
    <label className="col-span-3 text-sm text-gray-600 dark:text-gray-300">
      {label}{required && <span className="text-red-500 dark:text-red-400">*</span>}
    </label>
    <div className="col-span-9">{children}</div>
  </div>
);


const ModelProvidersSettings: React.FC = () => {
  const { t } = useTranslation();
  const toast = useContext(ToastContext);
  const { providers, isLoading, loadProviders, addProvider, updateProvider, removeProvider } = useProvidersStore();

  const [editingId, setEditingId] = useState<string | 'new' | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [reveal, setReveal] = useState<Record<string, boolean>>({});
  const [deleting, setDeleting] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [modelsLoading, setModelsLoading] = useState<boolean>(false);
  // Models combobox state
  const [isModelsOpen, setIsModelsOpen] = useState(false);
  const [modelsQuery, setModelsQuery] = useState('');
  const [modelOptions, setModelOptions] = useState<Array<{ id: string; name?: string }>>([]);
  const modelsBoxRef = useRef<HTMLDivElement | null>(null);
  // Global default models UI state
  const [chatOptions, setChatOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [embeddingOptions, setEmbeddingOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [llmSelection, setLlmSelection] = useState<string>('');
  const [embSelection, setEmbSelection] = useState<string>('');

  const {
    defaultLlmModel,
    defaultEmbeddingModel,
    setDefaultLlmModel,
    setDefaultEmbeddingModel,

  } = useAppSettingsStore();

  // Track last auto-filled name to avoid overriding custom user input
  const autoNameRef = useRef<string | null>(null);

  // Embedding help tooltip state
  const [showEmbeddingHelp, setShowEmbeddingHelp] = useState(false);
  const embeddingHelpRef = useRef<HTMLDivElement | null>(null);

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

  // Close embedding help tooltip when clicking outside
  useEffect(() => {
    if (!showEmbeddingHelp) return;
    const onDoc = (e: MouseEvent) => {
      if (embeddingHelpRef.current && !embeddingHelpRef.current.contains(e.target as Node)) {
        setShowEmbeddingHelp(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [showEmbeddingHelp]);

  // Reset options when provider kind changes in the current draft
  useEffect(() => {
    setModelOptions([]);
    setModelsQuery('');
    setIsModelsOpen(false);
  }, [draft?.kind]);

  const ensureFetchModelOptions = async (kind: ProviderKind, apiKey?: string, apiBaseUrl?: string) => {
    try {
      setModelsLoading(true);
      const service = new AIProvidersApiService();
      const providerKey = AIProvidersApiService.kindToProviderKey(kind);
      
      // Build request body for POST /v1/ai/models
      const requestBody: { provider: string; api_key?: string; api_base_url?: string; config?: Record<string, any> } = {
        provider: providerKey,
      };
      
      // Include api_key if provided (allows fetching actual models from provider)
      if (apiKey?.trim()) {
        requestBody.api_key = apiKey.trim();
      }
      
      // Include api_base_url if provided
      if (apiBaseUrl?.trim()) {
        requestBody.api_base_url = apiBaseUrl.trim();
      }
      
      // For Azure, include config with deployment info if available
      if (kind === 'azure' && draft?.params?.azure) {
        requestBody.config = {
          deployment: draft.params.azure.deployment,
          resource: draft.params.azure.resource,
          api_version: draft.params.azure.apiVersion,
        };
      }
      
      const res = await service.listModels(requestBody);
      // Response uses ModelListResponse format: { provider, models: ModelInfo[], is_fallback }
      const opts = (res.models || []).map((m: any) => ({ id: m.id, name: m.name })).filter((o: any) => o.id);
      setModelOptions(opts);
    } catch (e: any) {
      toast?.showToast('error', t('settings.providers.fetchModels.failed', '获取模型失败'), e?.message);
    } finally {
      setModelsLoading(false);
    }
  };


  const providerOptions: Array<{ value: ProviderKind; label: string; hint?: string }> = useMemo(() => [
    { value: 'openai', label: t('settings.providers.provider.openai', 'OpenAI'), hint: 'https://api.openai.com/v1' },
    { value: 'azure', label: t('settings.providers.provider.azure', 'Azure OpenAI'), hint: 'https://{resource}.openai.azure.com' },
    { value: 'qwen', label: t('settings.providers.provider.qwen', '通义千问 (DashScope)'), hint: 'https://dashscope.aliyuncs.com' },
    { value: 'moonshot', label: t('settings.providers.provider.moonshot', '月之暗面 (Kimi)'), hint: 'https://api.moonshot.cn' },
    { value: 'deepseek', label: t('settings.providers.provider.deepseek', 'DeepSeek'), hint: 'https://api.deepseek.com' },
    { value: 'baichuan', label: t('settings.providers.provider.baichuan', '百川'), hint: 'https://api.baichuan-ai.com' },
    { value: 'ollama', label: t('settings.providers.provider.ollama', 'Ollama'), hint: 'http://localhost:11434' },
    { value: 'custom', label: t('settings.providers.provider.custom', '自定义'), hint: t('settings.providers.placeholders.baseUrl.custom', '自定义 Base URL') },
  ], [t]);

  useEffect(() => {
    loadProviders().catch(() => {});
  }, [loadProviders]);

  const providerLabel = (kind: ProviderKind) => providerOptions.find(o => o.value === kind)?.label || kind;

  const startAdd = () => {
    setEditingId('new');
    const d = emptyDraft(t);
    setDraft(d);
    autoNameRef.current = d.name || '';
  };

  const startEdit = (p: ModelProviderConfig) => {
    setEditingId(p.id);
    setDraft({ ...p });
    autoNameRef.current = null; // do not auto-fill name in edit mode
  };

  const cancelEdit = () => { setEditingId(null); setDraft(null); };

  const saveDraft = async () => {
    if (!draft) return;
    // basic validation
    if (!draft.apiKey?.trim() && (editingId === 'new' || !draft.id)) {
      toast?.showToast('warning', t('settings.providers.validate.apiKey', '请输入 API Key'));
      return;
    }
    if (draft.kind === 'azure' && !draft.params?.azure?.deployment) {
      toast?.showToast('warning', t('settings.providers.validate.azureDeployment', '请输入 Azure 部署名称'));
      return;
    }

    try {
      if (editingId === 'new' || !draft.id) {
        const models = (draft.models || []).map(m => m.trim()).filter(Boolean);
        const defaultModel = draft.defaultModel && models.includes(draft.defaultModel.trim())
          ? draft.defaultModel.trim()
          : (models[0] || '');
        await addProvider({
          kind: draft.kind,
          name: draft.name?.trim() || providerLabel(draft.kind),
          apiKey: draft.apiKey.trim(),
          apiBaseUrl: draft.apiBaseUrl?.trim(),
          models,
          defaultModel,
          enabled: !!draft.enabled,
          params: draft.params,
        });
        setEditingId(null); setDraft(null);
        toast?.showToast('success', t('settings.providers.toast.added', '已添加提供商'));
      } else {
        const models = (draft.models || []).map(m => m.trim()).filter(Boolean);
        const defaultModel = draft.defaultModel && models.includes(draft.defaultModel.trim())
          ? draft.defaultModel.trim()
          : (models[0] || '');
        await updateProvider(draft.id, {
          kind: draft.kind,
          name: draft.name?.trim() || providerLabel(draft.kind),
          apiKey: (draft.apiKey || '').trim(),
          apiBaseUrl: draft.apiBaseUrl?.trim(),
          models,
          defaultModel,
          enabled: !!draft.enabled,
          params: draft.params,
        });
        setEditingId(null); setDraft(null);
        toast?.showToast('success', t('settings.providers.toast.saved', '已保存修改'));
      }
    } catch (e: any) {
      toast?.showToast('error', t('common.saveFailed', '保存失败'), e?.message);
    }
  };

  const onDelete = async (id: string) => {
    setDeleting(null);
    try {
      await removeProvider(id);
      toast?.showToast('success', t('settings.providers.toast.deleted', '已删除提供商'));
    } catch (e: any) {
      toast?.showToast('error', t('common.deleteFailed', '删除失败'), e?.message);
    }
  };

  // ===== Global Default Models logic =====
  // Sync UI selections from persisted store
  // Sync UI selections from persisted store
  useEffect(() => {
    setLlmSelection(defaultLlmModel || '');
    setEmbSelection(defaultEmbeddingModel || '');
  }, [defaultLlmModel, defaultEmbeddingModel]);

  const projectId = useAuthStore(s => s.user?.project_id);
  // Load project-level AI defaults from backend and reflect
  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    (async () => {
      try {
        const svc = new ProjectConfigApiService();
        const conf = await svc.getAIConfig(projectId);
        if (cancelled) return;
        const llm = conf.default_chat_provider_id && conf.default_chat_model
          ? `${conf.default_chat_provider_id}:${conf.default_chat_model}`
          : '';
        const emb = conf.default_embedding_provider_id && conf.default_embedding_model
          ? `${conf.default_embedding_provider_id}:${conf.default_embedding_model}`
          : '';
        setLlmSelection(llm);
        setEmbSelection(emb);
        setDefaultLlmModel(llm || null);
        setDefaultEmbeddingModel(emb || null);
      } catch (err: any) {
        toast?.showToast('error', t('common.loadFailed', '加载失败'), err?.message);
      }
    })();
    return () => { cancelled = true; };
  }, [projectId]);

  // Enabled provider keys for filtering models (maps ProviderKind to provider key used by models)
  const enabledProviderKeys = useMemo(() => {
    const enabled = providers.filter(p => p.enabled);
    return new Set(enabled.map(p => AIProvidersApiService.kindToProviderKey(p.kind)));
  }, [providers]);

  // Lazy load options on first open
  const [chatLoaded, setChatLoaded] = useState(false);
  const [embLoaded, setEmbLoaded] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [embLoading, setEmbLoading] = useState(false);

  const ensureFetchChatOptions = async () => {
    // Only prevent concurrent requests, but always refresh data on each click
    if (chatLoading) return;
    setChatLoading(true);
    try {
      const svc = new AIProvidersApiService();
      const res = await svc.listProviders({ is_active: true, model_type: 'chat', limit: 100, offset: 0 });
      const normalize = (list: any[]) =>
        (list || [])
          .filter((p: any) => enabledProviderKeys.has(p.provider) && Array.isArray(p.available_models) && p.available_models.length > 0)
          .flatMap((p: any) => (p.available_models || []).map((m: string) => ({ value: `${p.id}:${m}`, label: `${m} · ${p.name || p.provider}` })));
      setChatOptions(normalize(res.data || []));
      setChatLoaded(true);
    } catch (err: any) {
      toast?.showToast('error', t('common.loadFailed', '加载失败'), err?.message);
    } finally {
      setChatLoading(false);
    }
  };

  const ensureFetchEmbeddingOptions = async () => {
    // Only prevent concurrent requests, but always refresh data on each click
    if (embLoading) return;
    setEmbLoading(true);
    try {
      const svc = new AIProvidersApiService();
      const res = await svc.listProviders({ is_active: true, model_type: 'embedding', limit: 100, offset: 0 });
      const normalize = (list: any[]) =>
        (list || [])
          .filter((p: any) => enabledProviderKeys.has(p.provider) && Array.isArray(p.available_models) && p.available_models.length > 0)
          .flatMap((p: any) => (p.available_models || []).map((m: string) => ({ value: `${p.id}:${m}`, label: `${m} · ${p.name || p.provider}` })));
      setEmbeddingOptions(normalize(res.data || []));
      setEmbLoaded(true);
    } catch (err: any) {
      toast?.showToast('error', t('common.loadFailed', '加载失败'), err?.message);
    } finally {
      setEmbLoading(false);
    }
  };


	  // If backend returned saved selections, proactively load options so labels can display after refresh
	  useEffect(() => {
    if (enabledProviderKeys.size === 0) return;

	    if (llmSelection && !chatLoaded && !chatLoading) {
	      // Trigger lazy load for chat options to show the selected label
	      void ensureFetchChatOptions();
	    }
	  }, [llmSelection, chatLoaded, chatLoading, enabledProviderKeys]);



	  useEffect(() => {
    if (enabledProviderKeys.size === 0) return;

	    if (embSelection && !embLoaded && !embLoading) {
	      // Trigger lazy load for embedding options to show the selected label
	      void ensureFetchEmbeddingOptions();
	    }
	  }, [embSelection, embLoaded, embLoading, enabledProviderKeys]);

  // Options have been normalized and pre-filtered by enabled providers
  const filteredChatModels = chatOptions;
  const filteredEmbeddingModels = embeddingOptions;

  const onSaveDefaults = async () => {
    // Require both selections (LLM and Embedding)
    if (!llmSelection || !embSelection) {
      toast?.showToast('error', t('settings.models.toast.required', '请同时设置默认 LLM 和默认 Embedding 模型'));
      return;
    }
    if (!projectId) {
      toast?.showToast('error', t('common.saveFailed', '保存失败'), t('common.noProject', '缺少项目上下文'));
      return;
    }
    const parse = (v: string) => {
      const i = v.indexOf(':');
      if (i <= 0) return null;
      return { providerId: v.slice(0, i), model: v.slice(i + 1) } as const;
    };
    const chat = llmSelection ? parse(llmSelection) : null;
    const emb = embSelection ? parse(embSelection) : null;
    if (!chat || !emb) {
      // Either invalid or empty
      toast?.showToast('error', t('settings.models.toast.required', '请同时设置默认 LLM 和默认 Embedding 模型'));
      return;
    }
    try {
      const svc = new ProjectConfigApiService();
      await svc.upsertAIConfig(projectId, {
        default_chat_provider_id: chat ? chat.providerId : null,
        default_chat_model: chat ? chat.model : null,
        default_embedding_provider_id: emb ? emb.providerId : null,
        default_embedding_model: emb ? emb.model : null,
      });
      setDefaultLlmModel(llmSelection || null);
      setDefaultEmbeddingModel(embSelection || null);
      toast?.showToast('success', t('settings.models.toast.saved', '默认模型已保存'));
    } catch (err: any) {
      toast?.showToast('error', t('common.saveFailed', '保存失败'), err?.message);
    }
  };

  const testConnection = async (p: ModelProviderConfig) => {
    setTestingId(p.id);
    try {
      // use backend test endpoint to avoid CORS and keep key server-side
      const svc = new AIProvidersApiService();
      const res = await svc.testProvider(p.id);
      const ok = Boolean((res as any).ok ?? (res as any).success ?? true);
      if (ok) {
        toast?.showToast('success', t('settings.providers.test.ok', '连接成功'));
      } else {
        const detail = (res as any)?.details?.error?.message
          || (res as any)?.error?.message
          || (res as any)?.message
          || (res as any)?.detail
          || undefined;
        toast?.showToast('error', t('settings.providers.test.failed', '连接失败'), detail, 6000);
      }
    } catch (err: any) {
      const detail = err?.data?.details?.error?.message || err?.data?.error?.message || err?.message || String(err);
      toast?.showToast('error', t('settings.providers.test.failed', '连接失败'), detail, 6000);
    } finally {
      setTestingId(null);
    }
  };


  // models combobox will auto-fetch on focus/open; removed the old manual fetch button


  const renderEditForm = (d: Draft, idForState: string) => {
    const selected = providerOptions.find(o => o.value === d.kind);
    return (
      <div className="mt-4 space-y-4">
        <FieldRow label={t('settings.providers.fields.kind', '提供商')} required>
          <select
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={d.kind}
            onChange={(e) => {
              const kind = e.target.value as ProviderKind;
              const next: Draft = { ...d, kind };
              // 根据提供商类型自动填充 Base URL（使用 providerOptions.hint）；自定义则置空
              const selectedOpt = providerOptions.find(o => o.value === kind);
              const defaultBaseUrl = kind === 'custom' ? '' : (selectedOpt?.hint || '');
              // 新建时或当前值为空时才自动填充；编辑模式下已有值不覆盖
              if (editingId === 'new' || !(d.apiBaseUrl || '').trim()) {
                next.apiBaseUrl = defaultBaseUrl;
              }
              // 切换提供商类型时清空已选择的模型，避免不匹配
              next.models = [];
              next.defaultModel = '';

              // 自动填充名称：仅在新建模式下，且当前名称为空或为之前的默认值时
              if (editingId === 'new') {
                const currentName = (d.name || '').trim();
                const prevAuto = autoNameRef.current || '';
                const defaultName = t('settings.providers.defaultName', '新提供商') as string;
                const shouldAutofill = !currentName || currentName === prevAuto || currentName === providerLabel(d.kind) || currentName === defaultName;
                if (shouldAutofill) {
                  const label = providerLabel(kind);
                  next.name = label;
                  autoNameRef.current = label;
                }
              }

              setDraft(next);
            }}
          >
            {providerOptions.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </FieldRow>

        <FieldRow label={t('settings.providers.fields.name', '名称/别名')}>
          <input
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={d.name}
            onChange={(e) => setDraft({ ...d, name: e.target.value })}
            placeholder={providerLabel(d.kind)}
          />
        </FieldRow>

        <div className="pt-1 text-xs font-medium text-gray-700 dark:text-gray-200 border-t border-gray-100 dark:border-gray-700 mt-2">
          {t('settings.providers.groups.connection', '认证与连接')}
        </div>


        <FieldRow label={t('settings.providers.fields.apiKey', 'API Key')} required>
          <div className="flex items-center gap-2">
            <input
              type={reveal[idForState] ? 'text' : 'password'}
              className="flex-1 rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={d.apiKey || ''}
              onChange={(e) => setDraft({ ...d, apiKey: e.target.value })}
              placeholder={d.hasApiKey && d.apiKeyMasked ? (t('settings.providers.placeholders.apiKeyMasked', `已配置：${d.apiKeyMasked}，留空则不更新`) as string) : (t('settings.providers.placeholders.apiKey', '粘贴密钥') as string)}
            />
            <button
              type="button"
              onClick={() => setReveal((s) => ({ ...s, [idForState]: !s[idForState] }))}
              className="p-2 rounded border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
              title={reveal[idForState] ? t('common.hide', '隐藏') : t('common.show', '显示')}
            >
              {reveal[idForState] ? <FiEyeOff /> : <FiEye />}
            </button>
          </div>
        </FieldRow>

        <FieldRow label={t('settings.providers.fields.baseUrl', 'API Base URL')} required={d.kind !== 'ollama'}>
          <input
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={d.apiBaseUrl || ''}
            onChange={(e) => setDraft({ ...d, apiBaseUrl: e.target.value })}
            placeholder={selected?.hint}
          />
        </FieldRow>

        {d.kind === 'azure' && (
          <div className="grid grid-cols-12 gap-3">
            <div className="col-span-12 md:col-span-4">
              <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">{t('settings.providers.fields.azure.deployment', 'Deployment Name')}</label>
              <input
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={d.params?.azure?.deployment || ''}
                onChange={(e) => setDraft({ ...d, params: { ...d.params, azure: { ...(d.params?.azure || {}), deployment: e.target.value } } })}
                placeholder="gpt-4o"
              />
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('settings.providers.help.azure.deployment', 'Azure 中的部署名称，区别于模型 ID')}</div>

            </div>
            <div className="col-span-6 md:col-span-4">
              <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">{t('settings.providers.fields.azure.resource', 'Resource')}</label>
              <input
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={d.params?.azure?.resource || ''}
                onChange={(e) => setDraft({ ...d, params: { ...d.params, azure: { ...(d.params?.azure || {}), resource: e.target.value } } })}
                placeholder="my-azure-resource"
              />
              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('settings.providers.help.azure.resource', 'Azure 资源名称，例如 OpenAI 服务资源名')}</div>
            </div>
            <div className="col-span-6 md:col-span-4">
              <label className="block text-sm text-gray-600 dark:text-gray-300 mb-1">{t('settings.providers.fields.azure.apiVersion', 'API Version')}</label>
              <input
                className="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={d.params?.azure?.apiVersion || '2024-02-15-preview'}
                onChange={(e) => setDraft({ ...d, params: { ...d.params, azure: { ...(d.params?.azure || {}), apiVersion: e.target.value } } })}
                placeholder="2024-02-15-preview"
              />


          {t('settings.providers.groups.models', '')}



              <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{t('settings.providers.help.azure.apiVersion', 'Azure OpenAI API 版本号，如 2024-02-15-preview')}</div>
            </div>

          </div>


        )}


        <div className="pt-1 text-xs font-medium text-gray-700 dark:text-gray-200 border-t border-gray-100 dark:border-gray-700 mt-3 mb-1">
          {t('settings.providers.groups.modelsTitle', '模型与默认值')}
        </div>

        <FieldRow label={t('settings.providers.fields.models', '可用模型列表')}>
          <div className="relative" ref={modelsBoxRef}>


            <div
              className="flex flex-wrap items-center gap-1 rounded-md border border-gray-300 dark:border-gray-600 px-2 py-1 focus-within:ring-2 focus-within:ring-blue-500 hover:border-gray-400 dark:hover:border-gray-500 transition-colors"
              onClick={() => { ensureFetchModelOptions(d.kind, d.apiKey, d.apiBaseUrl); setIsModelsOpen(true); }}
            >
              {(d.models || []).map((m, idx) => (
                <span key={`${m}-${idx}`} className="inline-flex items-center px-2 py-0.5 text-xs border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-700 dark:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors">
                  <span className="truncate max-w-[140px]">{m}</span>
                  <button
                    type="button"
                    className="ml-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                    onClick={(e) => {
                      e.stopPropagation();
                      const next = (d.models || []).filter(x => x !== m);
                      const nextDefault = (d.defaultModel && next.includes(d.defaultModel)) ? d.defaultModel : (next[0] || '');
                      setDraft({ ...d, models: next, defaultModel: nextDefault });
                    }}
                    aria-label={t('common.remove', '移除') || '移除'}
                  >
                    ×
                  </button>
                </span>
              ))}
              <input
                className="flex-1 min-w-[120px] outline-none bg-transparent dark:text-gray-100 text-sm py-1"
                value={modelsQuery}
                onChange={(e) => setModelsQuery(e.target.value)}
                onFocus={() => { ensureFetchModelOptions(d.kind, d.apiKey, d.apiBaseUrl); setIsModelsOpen(true); }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const val = modelsQuery.trim();
                    if (val) {
                      const exists = (d.models || []).includes(val);
                      if (!exists) {
                        const next = [...(d.models || []), val];
                        const nextDefault = d.defaultModel && next.includes(d.defaultModel) ? d.defaultModel : (next[0] || '');
                        setDraft({ ...d, models: next, defaultModel: nextDefault });
                      }
                      setModelsQuery('');
                    }
                    e.preventDefault();
                  }
                }}
                placeholder={t('settings.providers.placeholders.modelsSearch', '搜索或输入模型ID...') || '搜索或输入模型ID...'}
              />
            </div>
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {t('settings.providers.help.modelsCustom', '如果列表为空或未找到所需模型，您可以手动输入自定义模型名称')}
            </div>


            {isModelsOpen && (
              <div className="absolute z-20 mt-1 w-full max-h-64 overflow-auto rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg">
                <div className="p-2">
                  {modelsLoading ? (
                    <div className="flex items-center text-sm text-gray-500 dark:text-gray-400"><FiLoader className="animate-spin mr-2" />{t('common.loading', '加载中...')}</div>
                  ) : (
                    <>
                      {(() => {
                        const q = modelsQuery.trim().toLowerCase();
                        const selected = new Set(d.models || []);
                        const list = (modelOptions || []).filter(opt => {
                          const id = (opt.id || '').toLowerCase();
                          const name = (opt.name || '').toLowerCase();
                          return !q || id.includes(q) || name.includes(q);
                        });
                        return (
                          <>
                            {q && !(d.models || []).includes(modelsQuery.trim()) && !list.some(opt => opt.id === modelsQuery.trim()) && (
                              <button
                                type="button"
                                className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 rounded dark:text-gray-100"
                                onClick={() => {
                                  const val = modelsQuery.trim();
                                  if (!val) return;
                                  const next = Array.from(new Set([...(d.models || []), val]));
                                  const nextDefault = d.defaultModel && next.includes(d.defaultModel) ? d.defaultModel : (next[0] || '');
                                  setDraft({ ...d, models: next, defaultModel: nextDefault });
                                  setModelsQuery('');
                                  setIsModelsOpen(false);
                                }}
                              >
                                {t('settings.providers.createModelOption', '创建')} "{modelsQuery.trim()}"
                              </button>
                            )}
                            {list.length === 0 && !q && (
                              <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">{t('settings.providers.fetchModels.empty', '没有可用模型')}</div>
                            )}
                            {list.map(opt => {
                              const active = selected.has(opt.id);
                              return (
                                <button
                                  type="button"
                                  key={opt.id}
                                  className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 rounded transition-colors ${active ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'dark:text-gray-100'}`}
                                  onClick={() => {
                                    let next = active ? (d.models || []).filter(m => m !== opt.id) : Array.from(new Set([...(d.models || []), opt.id]));
                                    const nextDefault = d.defaultModel && next.includes(d.defaultModel) ? d.defaultModel : (next[0] || '');
                                    setDraft({ ...d, models: next, defaultModel: nextDefault });
                                  }}
                                >
                                  <div className="flex items-center justify-between">
                                    <div className="min-w-0">
                                      <div className="truncate">{opt.id}</div>
                                      {opt.name ? <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{opt.name}</div> : null}
                                    </div>
                                    {active ? <span className="text-xs text-blue-600 dark:text-blue-400">{t('common.selected', '已选择')}</span> : null}
                                  </div>
                                </button>
                              );
                            })}
                          </>
                        );

                      })()}
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </FieldRow>

        <FieldRow label={t('settings.providers.fields.defaultModel', '默认模型')}>
          <select
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={d.defaultModel || ''}
            onChange={(e) => setDraft({ ...d, defaultModel: e.target.value })}
            disabled={!d.models || d.models.length === 0}
          >
            <option value="" disabled>{t('settings.providers.selectDefaultModel', '请先添加模型')}</option>
            {(d.models || []).map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </FieldRow>

        <FieldRow label={t('settings.providers.enableButton', '启用')}>
          <Toggle checked={!!d.enabled} onChange={(v) => setDraft({ ...d, enabled: v })} />
        </FieldRow>

        <div className="flex items-center gap-2 pt-4 mt-2 border-t border-gray-100 dark:border-gray-700">
          <Button variant="primary" size="md" onClick={saveDraft}>{t('common.save', '保存')}</Button>
          <Button variant="secondary" size="md" onClick={cancelEdit}>{t('common.cancel', '取消')}</Button>
        </div>
      </div>
    );
  };

  const sortedProviders = useMemo(() => providers.slice().sort((a, b) => Number(b.enabled) - Number(a.enabled)), [providers]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FiCpu className="w-5 h-5 text-gray-600 dark:text-gray-300" />
          <h2 className="text-lg font-medium text-gray-800 dark:text-gray-100">{t('settings.providers.title', '模型提供商')}</h2>
        </div>
        <div className="flex items-center gap-2">
          {isLoading && <FiLoader className="animate-spin text-gray-400 dark:text-gray-500" />}
          <Button variant="primary" size="md" onClick={startAdd} disabled={isLoading}>
            <FiPlus className="mr-1" />{t('settings.providers.add', '添加提供商')}
          </Button>
        </div>
      </div>

      {/* 页面说明 */}
      <div className="text-sm text-gray-600 dark:text-gray-300">
        {t('settings.providers.subtitle', '集中管理各大 AI 提供商的访问配置：密钥、安全代理、模型清单与默认模型。')}
      </div>


      {/* Global Default Models Card */}
      <SectionCard>
        <SectionHeader title={t('settings.models.defaults.title', '默认模型')} />
        <div className="text-sm text-gray-600 dark:text-gray-300 mb-3">
          {t('settings.models.defaults.description', '选择全局默认的 LLM 和嵌入模型，具体页面可覆盖。')}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
              {t('settings.models.defaults.llmLabel', '默认 LLM')}
            </label>
            <select
              className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 focus:border-gray-400 focus:ring-0"
              value={llmSelection}
              onChange={(e) => setLlmSelection(e.target.value)}
              onFocus={ensureFetchChatOptions}
            >
              <option value="">{t('settings.models.defaults.none', '未设置')}</option>
              {chatLoading && <option value="" disabled>{t('common.loading', '加载中...')}</option>}
              {filteredChatModels.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center gap-1 mb-1">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-200">
                {t('settings.models.defaults.embeddingLabel', '默认嵌入模型')}
              </label>
              <div className="relative" ref={embeddingHelpRef}>
                <button
                  type="button"
                  onClick={() => setShowEmbeddingHelp(!showEmbeddingHelp)}
                  className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                  aria-label="查看推荐的嵌入模型"
                >
                  <FiHelpCircle className="w-4 h-4" />
                </button>
                {showEmbeddingHelp && (
                  <div className="absolute left-0 top-6 z-50 w-80 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 p-4">
                    <h4 className="text-sm font-semibold text-gray-800 dark:text-gray-100 mb-3">
                      {t('settings.models.defaults.embeddingHelp.title', '推荐的嵌入模型')}
                    </h4>
                    <div className="space-y-3">
                      <div>
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                          {t('settings.models.defaults.embeddingHelp.providers.openai.name', 'OpenAI')}
                        </div>
                        <ul className="text-xs text-gray-600 dark:text-gray-300 space-y-1 ml-2">
                          <li>• text-embedding-3-small</li>
                          <li>• text-embedding-3-large</li>
                          <li>• text-embedding-ada-002</li>
                        </ul>
                      </div>
                      <div>
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
                          {t('settings.models.defaults.embeddingHelp.providers.qwen.name', '千问/DashScope')}
                        </div>
                        <ul className="text-xs text-gray-600 dark:text-gray-300 space-y-1 ml-2">
                          <li>• text-embedding-v4</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
            <select
              className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 focus:border-gray-400 focus:ring-0"
              value={embSelection}
              onChange={(e) => setEmbSelection(e.target.value)}
              onFocus={ensureFetchEmbeddingOptions}
            >
              <option value="">{t('settings.models.defaults.none', '未设置')}</option>
              {embLoading && <option value="" disabled>{t('common.loading', '加载中...')}</option>}
              {filteredEmbeddingModels.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <Button variant="primary" size="md" onClick={onSaveDefaults}>{t('common.save', '保存')}</Button>
        </div>
      </SectionCard>


      {/* 添加/编辑表单（新建） */}
      {editingId === 'new' && draft && (
        <SectionCard>
          <SectionHeader icon={<FiCpu className="w-5 h-5 text-gray-600" />} title={t('settings.providers.addTitle', '新增提供商')} />
          {renderEditForm(draft, 'new')}
        </SectionCard>
      )}

      {/* 已配置列表 */}
      <div className="space-y-4">
        {sortedProviders.length === 0 && editingId !== 'new' && (
          <div className="bg-white dark:bg-gray-800 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700 p-10 text-center text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
            <div className="flex flex-col items-center gap-2">
              <FiCpu className="w-8 h-8 text-gray-400 dark:text-gray-500" />
              <div>{t('settings.providers.empty', '尚未配置任何模型提供商，点击右上角"添加提供商"开始。')}</div>
              <div>
                <Button variant="primary" size="md" onClick={startAdd}>
                  <FiPlus className="mr-1" />{t('settings.providers.add', '添加提供商')}
                </Button>
              </div>
            </div>
          </div>
        )}

        {sortedProviders.map((p) => (
          <SectionCard key={p.id} className="transition-shadow hover:shadow-md hover:border-gray-300 dark:hover:border-gray-600">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="text-base font-medium text-gray-800 dark:text-gray-100">{p.name || providerLabel(p.kind)}</span>
                  <UIBadge variant={p.enabled ? 'success' : 'secondary'} size="md">{p.enabled ? t('settings.providers.enableButton', '启用') : t('common.disabled', '禁用')}</UIBadge>
                  {p.defaultModel ? (
                    <span className="inline-flex items-center px-2 py-0.5 text-xs rounded-md border bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700">
                      {t('settings.providers.badges.default', '默认')}: {p.defaultModel}
                    </span>
                  ) : null}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 flex flex-wrap items-center gap-x-3">
                  <span>{t('settings.providers.fields.kind', '提供商')}: {providerLabel(p.kind)}</span>
                  {p.apiBaseUrl && <span className="truncate max-w-[320px]">{t('settings.providers.baseUrl', 'Base URL')}: {p.apiBaseUrl}</span>}
                  <span className="text-gray-300 dark:text-gray-600">·</span>
                  <span>{t('settings.providers.updateButton', '更新')}: {new Date(p.updatedAt).toLocaleString()}</span>
                </div>
                {(p.models && p.models.length > 0) && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {p.models.map((m) => (
                      <span key={m} className={`px-2 py-0.5 text-[11px] rounded border ${p.defaultModel===m ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-700' : 'bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-600'}`}>
                        {m}{p.defaultModel===m ? ` · ${t('settings.providers.badges.default', '默认')}` : ''}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 pl-3 md:pl-4 border-l border-gray-100 dark:border-gray-700">
                <Button variant="secondary" size="sm" onClick={() => testConnection(p)} disabled={testingId === p.id}>
                  {testingId === p.id ? <FiLoader className="animate-spin mr-1" /> : null}
                  {t('settings.providers.testButton', '测试连接')}
                </Button>
                <Button variant="secondary" size="sm" onClick={() => startEdit(p)}>
                  <FiEdit2 className="mr-1" />{t('common.edit', '编辑')}
                </Button>
                <Button variant="danger" size="sm" onClick={() => setDeleting(p.id)}>
                  <FiTrash2 className="mr-1" />{t('common.delete', '删除')}
                </Button>
              </div>
            </div>

            {editingId === p.id && draft && draft.id === p.id && (
              <div className="pt-2 border-t border-gray-200 dark:border-gray-700 mt-4">
                {renderEditForm(draft as Draft, p.id)}
              </div>
            )}
          </SectionCard>
        ))}
      </div>

      <ConfirmDialog
        isOpen={!!deleting}
        title={t('settings.providers.confirmDeleteTitle', '删除提供商')}
        message={t('settings.providers.confirmDeleteMsg', '确定要删除该提供商配置吗？此操作不可撤销。')}
        confirmText={t('common.delete', '删除')!}
        cancelText={t('common.cancel', '取消')!}
        confirmVariant="danger"
        onConfirm={() => deleting && onDelete(deleting)}
        onCancel={() => setDeleting(null)}
      />
    </div>
  );
};

export default ModelProvidersSettings;

