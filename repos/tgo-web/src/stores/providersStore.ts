import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import AIProvidersApiService, { type AIProviderResponseDTO } from '@/services/aiProvidersApi';

export type ProviderKind = 'openai' | 'azure' | 'qwen' | 'moonshot' | 'deepseek' | 'baichuan' | 'ollama' | 'custom';

export interface AzureExtra {
  deployment?: string;
  resource?: string;
  apiVersion?: string; // e.g. 2024-02-15-preview
}

export interface ProviderParams {
  azure?: AzureExtra;
  // extend for other providers if needed
  [key: string]: any;
}

export interface ModelProviderConfig {
  id: string;
  kind: ProviderKind;
  name: string; // display name/alias
  apiKey: string; // not returned by backend; kept only for editing
  apiBaseUrl?: string;
  // Multi-model support
  models?: string[]; // list of model identifiers available under this provider
  defaultModel?: string; // must be one of models if models exists
  enabled: boolean;
  params?: ProviderParams;
  createdAt: number;
  updatedAt: number;
  // backend-only metadata for display
  hasApiKey?: boolean;
  apiKeyMasked?: string | null;
  storeResourceId?: string | null;
  isFromStore?: boolean;
}

export interface ProvidersState {
  providers: ModelProviderConfig[];
  isLoading: boolean;
  error: string | null;
  loadProviders: () => Promise<void>;
  addProvider: (data: Omit<ModelProviderConfig, 'id' | 'createdAt' | 'updatedAt'>) => Promise<string>;
  updateProvider: (id: string, patch: Partial<ModelProviderConfig>) => Promise<void>;
  removeProvider: (id: string) => Promise<void>;
  addModelToProvider: (providerId: string, models: Array<{ model_id: string; model_type: 'chat' | 'embedding' }>) => Promise<void>;
  removeModelFromProvider: (providerId: string, modelId: string) => Promise<void>;
  clearAll: () => void;
}

const svc = new AIProvidersApiService();

function mapDtoToConfig(dto: AIProviderResponseDTO): ModelProviderConfig {
  const kind = AIProvidersApiService.providerKeyToKind(dto.provider);
  const models = (dto.available_models || []).filter(Boolean);
  const defaultModel = dto.default_model || (models[0] || undefined);
  const createdAt = Date.parse(dto.created_at) || Date.now();
  const updatedAt = Date.parse(dto.updated_at) || createdAt;
  return {
    id: dto.id,
    kind,
    name: dto.name,
    apiKey: '', // backend never returns secret; keep empty unless user edits
    apiBaseUrl: dto.api_base_url || undefined,
    models,
    defaultModel,
    enabled: !!dto.is_active,
    params: AIProvidersApiService.extractParams(kind, dto.config),
    createdAt,
    updatedAt,
    hasApiKey: dto.has_api_key,
    apiKeyMasked: dto.api_key_masked ?? null,
    storeResourceId: dto.store_resource_id ?? null,
    isFromStore: !!dto.is_from_store,
  };
}

export const useProvidersStore = create<ProvidersState>()(
  devtools(
    (set, get) => ({
      providers: [],
      isLoading: false,
      error: null,

      loadProviders: async () => {
        set({ isLoading: true, error: null });
        try {
          const res = await svc.listProviders({ limit: 100, offset: 0 });
          const list = (res.data || []).map(mapDtoToConfig);
          set({ providers: list, isLoading: false });
        } catch (e: any) {
          set({ isLoading: false, error: e?.message || '加载失败' });
        }
      },

      addProvider: async (data) => {
        // normalize models/defaultModel for multi-model support
        const models = Array.isArray((data as any).models) ? ([...((data as any).models as string[])].filter(Boolean)) : [];
        const defaultModel = (data as any).defaultModel || (models.length > 0 ? models[0] : undefined);
        if (defaultModel && !models.includes(defaultModel)) models.push(defaultModel);

        const payload = {
          provider: AIProvidersApiService.kindToProviderKey(data.kind),
          name: data.name,
          api_key: data.apiKey,
          api_base_url: data.apiBaseUrl || null,
          available_models: models.length ? models : [],
          default_model: defaultModel || null,
          config: AIProvidersApiService.buildBackendConfig(data.kind, data.params) || null,
          is_active: !!data.enabled,
        };
        const created = await svc.createProvider(payload);
        const cfg = mapDtoToConfig(created);
        set((state) => ({ providers: [...state.providers, cfg] }));
        return cfg.id;
      },

      updateProvider: async (id, patch) => {
        // find current for fallback
        const current = get().providers.find(p => p.id === id);
        if (!current) return;
        const nextKind = patch.kind || current.kind;
        // normalize models/defaultModel
        let models = Array.isArray(patch.models) ? patch.models.filter(Boolean) : current.models || [];
        let defaultModel = patch.defaultModel ?? current.defaultModel;
        if (defaultModel && !models.includes(defaultModel)) models.push(defaultModel);
        if (!defaultModel && models.length > 0) defaultModel = models[0];

        const payload: any = {} as any;
        if (patch.kind) payload.provider = AIProvidersApiService.kindToProviderKey(patch.kind);
        if (patch.name !== undefined) payload.name = patch.name;
        if (patch.apiBaseUrl !== undefined) payload.api_base_url = patch.apiBaseUrl || null;
        if (patch.params !== undefined) payload.config = AIProvidersApiService.buildBackendConfig(nextKind, patch.params) || null;
        if (patch.enabled !== undefined) payload.is_active = !!patch.enabled;
        if (patch.models !== undefined || patch.defaultModel !== undefined) {
          payload.available_models = models.length ? models : [];
          payload.default_model = defaultModel || null;
        }
        if (patch.apiKey && patch.apiKey.trim() !== '') payload.api_key = patch.apiKey.trim();

        const updated = await svc.updateProvider(id, payload);
        const mapped = mapDtoToConfig(updated);
        set((state) => ({
          providers: state.providers.map(p => p.id === id ? mapped : p)
        }));
      },

      removeProvider: async (id) => {
        await svc.deleteProvider(id);
        set((state) => ({ providers: state.providers.filter(p => p.id !== id) }));
      },

      addModelToProvider: async (providerId, models) => {
        const current = get().providers.find(p => p.id === providerId);
        if (!current) return;
        
        // Fetch current model IDs
        const existingModelIds = current.models || [];
        
        // Merge with type info for new models, and assume 'chat' for existing ones if type unknown
        // Backend update_ai_provider will handle this
        const available_models: any[] = [
          ...existingModelIds.map(id => ({ model_id: id, model_type: 'chat' as const })),
          ...models.filter(m => !existingModelIds.includes(m.model_id))
        ];
        
        const updated = await svc.updateProvider(providerId, {
          available_models
        });
        
        const mapped = mapDtoToConfig(updated);
        set((state) => ({
          providers: state.providers.map(p => p.id === providerId ? mapped : p)
        }));
      },

      removeModelFromProvider: async (providerId, modelId) => {
        await svc.deleteModel(providerId, modelId);
        const current = get().providers.find(p => p.id === providerId);
        if (current) {
          const updatedModels = (current.models || []).filter(m => m !== modelId);
          set((state) => ({
            providers: state.providers.map(p => p.id === providerId ? { ...p, models: updatedModels } : p)
          }));
        }
      },

      clearAll: () => set({ providers: [] }),
    }),
    { name: 'providers-store' }
  )
);
