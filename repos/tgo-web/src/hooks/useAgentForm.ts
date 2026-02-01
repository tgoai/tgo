import { useCallback, useState } from 'react';
import type { AgentCategory } from '@/types';

export interface AgentFormState {
  name: string;
  profession: string;
  description: string;
  llmModel: string;
  agentCategory: AgentCategory;
  tools: string[];
  toolConfigs: Record<string, Record<string, any>>;
  knowledgeBases: string[];
  workflows: string[];
  boundDeviceId: string | null;
  // 高级配置
  markdown?: boolean;
  add_datetime_to_context?: boolean;
  tool_call_limit?: number;
  num_history_runs?: number;
}

export interface UseAgentFormOptions {
  initial?: Partial<AgentFormState>;
  // Controlled mode (e.g., Create modal uses store-backed form)
  controlledFormData?: AgentFormState;
  onFormDataChange?: (update: Partial<AgentFormState>) => void;
}

export interface UseAgentFormResult {
  formData: AgentFormState;
  setFormData: (update: Partial<AgentFormState>) => void;
  handleInputChange: (field: keyof AgentFormState, value: any) => void;
  // Tools
  removeTool: (toolId: string) => void;
  setToolConfig: (toolId: string, config: Record<string, any>) => void;
  // Knowledge bases
  removeKnowledgeBase: (kbId: string) => void;
  // Workflows
  removeWorkflow: (workflowId: string) => void;
  // Devices (for computer_use agents)
  removeDevice: (deviceId?: string) => void;
  // Reset
  reset: (next?: Partial<AgentFormState>) => void;
}

const defaultForm: AgentFormState = {
  name: '',
  profession: '',
  description: '',
  llmModel: 'gemini-1.5-pro',
  agentCategory: 'normal',
  tools: [],
  toolConfigs: {},
  knowledgeBases: [],
  workflows: [],
  boundDeviceId: null,
  markdown: true,
  add_datetime_to_context: true,
  tool_call_limit: 10,
  num_history_runs: 5,
};

export function useAgentForm(options: UseAgentFormOptions = {}): UseAgentFormResult {
  const {
    initial,
    controlledFormData,
    onFormDataChange,
  } = options;

  // Form data: controlled or uncontrolled
  const [uncontrolledForm, setUncontrolledForm] = useState<AgentFormState>({
    ...defaultForm,
    ...(initial || {}),
  });

  const formData = (controlledFormData || uncontrolledForm);

  const setFormData = useCallback((update: Partial<AgentFormState>) => {
    if (onFormDataChange) {
      onFormDataChange(update);
    } else {
      setUncontrolledForm(prev => ({ ...prev, ...update }));
    }
  }, [onFormDataChange]);

  const handleInputChange = useCallback((field: keyof AgentFormState, value: any) => {
    setFormData({ [field]: value } as Partial<AgentFormState>);
  }, [setFormData]);

  const removeTool = useCallback((toolId: string) => {
    // remove from list
    const newTools = (formData.tools || []).filter(id => id !== toolId);
    setFormData({ tools: newTools });
  }, [formData.tools, setFormData]);

  const setToolConfig = useCallback((toolId: string, config: Record<string, any>) => {
    setFormData({
      toolConfigs: {
        ...formData.toolConfigs,
        [toolId]: config,
      },
    });
  }, [formData.toolConfigs, setFormData]);

  // Knowledge bases
  const removeKnowledgeBase = useCallback((kbId: string) => {
    const newKBs = (formData.knowledgeBases || []).filter(id => id !== kbId);
    setFormData({ knowledgeBases: newKBs });
  }, [formData.knowledgeBases, setFormData]);

  // Workflows
  const removeWorkflow = useCallback((workflowId: string) => {
    const newWorkflows = (formData.workflows || []).filter(id => id !== workflowId);
    setFormData({ workflows: newWorkflows });
  }, [formData.workflows, setFormData]);

  // Devices (for computer_use agents)
  const removeDevice = useCallback((_deviceId?: string) => {
    setFormData({ boundDeviceId: null });
  }, [setFormData]);

  // Reset API
  const reset = useCallback((next?: Partial<AgentFormState>) => {
    if (next) {
      if (onFormDataChange) {
        onFormDataChange(next);
      } else {
        setUncontrolledForm({ ...defaultForm, ...next });
      }
    } else if (!onFormDataChange) {
      setUncontrolledForm({ ...defaultForm });
    }
  }, [onFormDataChange]);

  return {
    formData,
    setFormData,
    handleInputChange,
    removeTool,
    setToolConfig,
    removeKnowledgeBase,
    removeWorkflow,
    removeDevice,
    reset,
  };
}

export default useAgentForm;
