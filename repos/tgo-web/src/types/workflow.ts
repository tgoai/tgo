/**
 * Workflow Type Definitions
 * Defines all types related to AI Agent Workflows
 */

import type { Node } from 'reactflow';

// ============================================================================
// Node Types
// ============================================================================

/**
 * Available workflow node types
 */
export type WorkflowNodeType = 
  | 'input'      // 用户输入触发
  | 'timer'      // 定时触发
  | 'webhook'    // Webhook 触发
  | 'event'      // 事件触发
  | 'answer'     // 回复/输出节点
  | 'agent' 
  | 'tool' 
  | 'condition' 
  | 'llm' 
  | 'parallel'
  | 'api'
  | 'classifier';

/**
 * Base node data shared by all nodes
 */
export interface BaseNodeData {
  label: string;
  description?: string;
  reference_key?: string; // Stable English key for variable references, e.g., "llm_1"
}

/**
 * API node data - external HTTP call
 */
export interface APINodeData extends BaseNodeData {
  type: 'api';
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  url: string;
  headers?: { key: string; value: string }[];
  params?: { key: string; value: string }[];
  body_type: 'none' | 'json' | 'form-data' | 'x-www-form-urlencoded' | 'raw';
  body?: string; // For json and raw
  form_data?: { key: string; value: string; type: 'text' | 'file' }[];
  form_url_encoded?: { key: string; value: string }[];
  raw_type?: 'text' | 'html' | 'xml' | 'javascript';
}

/**
 * Input node data - user input trigger
 */
export interface InputNodeData extends BaseNodeData {
  type: 'input';
  input_variables?: { name: string; type: 'string' | 'number' | 'boolean'; description?: string }[];
}

/**
 * Timer node data - scheduled trigger
 */
export interface TimerNodeData extends BaseNodeData {
  type: 'timer';
  cron_expression: string;
}

/**
 * Webhook node data - HTTP callback trigger
 */
export interface WebhookNodeData extends BaseNodeData {
  type: 'webhook';
  path?: string; // Optional path suffix
  method?: 'GET' | 'POST';
}

/**
 * Event node data - internal system event trigger
 */
export interface EventNodeData extends BaseNodeData {
  type: 'event';
  event_type: string;
}

/**
 * Answer node data - response point of workflow
 */
export interface AnswerNodeData extends BaseNodeData {
  type: 'answer';
  output_type: 'variable' | 'template' | 'structured';
  output_variable?: string; // For 'variable' type
  output_template?: string; // For 'template' type
  output_structure?: { key: string; value: string }[]; // For 'structured' type
}

/**
 * Agent node data - calls another AI Agent
 */
export interface AgentNodeData extends BaseNodeData {
  type: 'agent';
  agent_id: string;
  agent_name?: string;
  input_mapping?: Record<string, string>;
}

/**
 * Tool node data - executes an MCP tool
 */
export interface ToolNodeData extends BaseNodeData {
  type: 'tool';
  tool_id: string;
  tool_name?: string;
  config?: Record<string, any>;
  input_mapping?: Record<string, string>;
}

/**
 * Condition node data - branching logic
 */
export interface ConditionNodeData extends BaseNodeData {
  type: 'condition';
  condition_type: 'expression' | 'variable' | 'llm';
  expression?: string;
  variable?: string;
  operator?: 'equals' | 'notEquals' | 'contains' | 'greaterThan' | 'lessThan' | 'isEmpty' | 'isNotEmpty';
  compare_value?: string;
  llm_prompt?: string;
  provider_id?: string;
  model_id?: string;
  model_name?: string;
}

/**
 * LLM node data - direct LLM call
 */
export interface LLMNodeData extends BaseNodeData {
  type: 'llm';
  provider_id?: string;
  model_id?: string;
  model_name?: string;
  system_prompt?: string;
  user_prompt: string;
  temperature?: number;
  max_tokens?: number;
  tools?: string[]; // IDs of selected MCP tools
  knowledge_bases?: string[]; // IDs of selected knowledge bases
}

/**
 * Parallel node data - parallel execution
 */
export interface ParallelNodeData extends BaseNodeData {
  type: 'parallel';
  branches: number;
  wait_for_all: boolean;
  timeout?: number;
}

/**
 * Classifier node data - categorizes input using LLM
 */
export interface ClassifierNodeData extends BaseNodeData {
  type: 'classifier';
  input_variable: string;
  provider_id?: string;
  model_id?: string;
  model_name?: string;
  categories: { id: string; name: string; description: string }[];
}

/**
 * Union type for all node data
 */
export type WorkflowNodeData = 
  | InputNodeData
  | TimerNodeData
  | WebhookNodeData
  | EventNodeData
  | AnswerNodeData
  | AgentNodeData 
  | ToolNodeData 
  | ConditionNodeData 
  | LLMNodeData 
  | ParallelNodeData
  | APINodeData
  | ClassifierNodeData;

/**
 * Workflow node extending React Flow Node
 */
export type WorkflowNode = Node<WorkflowNodeData, WorkflowNodeType>;

// ============================================================================
// Edge Types
// ============================================================================

/**
 * Edge label for conditional branches
 */
export type EdgeLabel = 'true' | 'false' | 'default' | string;

/**
 * Workflow edge extending React Flow Edge
 */
export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  type?: string;
  data?: Record<string, any>;
}

// ============================================================================
// Workflow Types
// ============================================================================

/**
 * Workflow status
 */
export type WorkflowStatus = 'draft' | 'active' | 'inactive' | 'archived';

/**
 * Workflow execution status
 */
export type WorkflowExecutionStatus = 
  | 'pending' 
  | 'running' 
  | 'completed' 
  | 'failed' 
  | 'cancelled';

/**
 * Workflow definition
 */
export interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

/**
 * Workflow record from DB
 */
export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  definition: WorkflowDefinition;
  status: WorkflowStatus;
  version: number;
  tags: string[];
  created_at: string;
  updated_at: string;
  created_by?: string | null;
}

/**
 * Workflow summary for list views
 */
export interface WorkflowSummary {
  id: string;
  name: string;
  description: string | null;
  status: WorkflowStatus;
  version: number;
  tags: string[];
  updated_at: string;
}

/**
 * Workflow execution record
 */
export interface WorkflowExecution {
  id: string;
  workflow_id: string;
  status: WorkflowExecutionStatus;
  input?: Record<string, any> | null;
  output?: Record<string, any> | null;
  error?: string | null;
  started_at: string;
  completed_at?: string | null;
  duration?: number | null;
  node_executions: NodeExecution[];
}

/**
 * Workflow execution stream events
 */
export type WorkflowStreamEvent = 
  | { event: 'workflow_started'; workflow_run_id: string; data: { id: string; workflow_id: string; inputs: any; created_at: number } }
  | { event: 'node_started'; workflow_run_id: string; data: { id: string; node_id: string; node_type: string; title: string; index: number } }
  | { event: 'node_finished'; workflow_run_id: string; data: { id: string; node_id: string; node_type: string; status: 'succeeded' | 'failed'; inputs: any; outputs: any; error?: string; elapsed_time: number } }
  | { event: 'workflow_finished'; workflow_run_id: string; data: { status: 'succeeded' | 'failed'; outputs: any; error?: string; total_steps: number; elapsed_time: number } };

/**
 * Individual node execution record
 */
export interface NodeExecution {
  id: string;
  execution_id: string;
  node_id: string;
  node_type: string;
  status: WorkflowExecutionStatus;
  input?: Record<string, any> | null;
  output?: Record<string, any> | null;
  error?: string | null;
  started_at: string;
  completed_at?: string | null;
  duration?: number | null;
}

// ============================================================================
// API Types
// ============================================================================

/**
 * Workflow create request
 */
export interface WorkflowCreateRequest {
  name: string;
  description?: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  tags?: string[];
}

/**
 * Workflow update request
 */
export interface WorkflowUpdateRequest {
  name?: string | null;
  description?: string | null;
  nodes?: WorkflowNode[] | null;
  edges?: WorkflowEdge[] | null;
  status?: WorkflowStatus | null;
  tags?: string[] | null;
}

/**
 * Workflow list response
 */
export interface WorkflowListResponse {
  data: WorkflowSummary[];
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

/**
 * Workflow query parameters
 */
export interface WorkflowQueryParams {
  status?: WorkflowStatus;
  search?: string;
  tags?: string[];
  limit?: number;
  offset?: number;
}

// ============================================================================
// Editor Types
// ============================================================================

/**
 * Node palette item for drag and drop
 */
export interface NodePaletteItem {
  type: WorkflowNodeType;
  label: string;
  description: string;
  icon: string;
  color: string;
  category: 'trigger' | 'ai' | 'logic' | 'external' | 'output';
}

// ============================================================================
// Editor Types
// ============================================================================

/**
 * Editor state
 */
export interface WorkflowEditorState {
  workflow: Workflow | null;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  isDirty: boolean;
  isValid: boolean;
  validationErrors: ValidationError[];
  history: HistoryState[];
  historyIndex: number;
}

/**
 * Validation error
 */
export interface ValidationError {
  nodeId?: string;
  edgeId?: string;
  message: string;
  severity: 'error' | 'warning';
}

/**
 * History state for undo/redo
 */
export interface HistoryState {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  timestamp: number;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Node type configurations
 */
export const NODE_TYPE_CONFIG: Record<WorkflowNodeType, NodePaletteItem> = {
  input: {
    type: 'input',
    label: '用户输入',
    description: '通过用户对话消息触发',
    icon: 'Play',
    color: 'green',
    category: 'trigger',
  },
  timer: {
    type: 'timer',
    label: '定时触发',
    description: '按设定的时间计划执行',
    icon: 'Clock',
    color: 'green',
    category: 'trigger',
  },
  webhook: {
    type: 'webhook',
    label: 'Webhook',
    description: '通过外部 HTTP 请求触发',
    icon: 'Globe',
    color: 'green',
    category: 'trigger',
  },
  event: {
    type: 'event',
    label: '事件触发',
    description: '通过系统内部事件触发',
    icon: 'Zap',
    color: 'green',
    category: 'trigger',
  },
  answer: {
    type: 'answer',
    label: '回复',
    description: '向用户或调用方返回结果',
    icon: 'MessageSquare',
    color: 'blue',
    category: 'output',
  },
  agent: {
    type: 'agent',
    label: 'AI Agent',
    description: '调用其他AI员工',
    icon: 'Bot',
    color: 'blue',
    category: 'ai',
  },
  tool: {
    type: 'tool',
    label: 'MCP工具',
    description: '执行MCP工具',
    icon: 'Wrench',
    color: 'orange',
    category: 'external',
  },
  condition: {
    type: 'condition',
    label: '条件判断',
    description: '根据条件分支',
    icon: 'GitBranch',
    color: 'purple',
    category: 'logic',
  },
  llm: {
    type: 'llm',
    label: 'LLM调用',
    description: '直接调用大语言模型',
    icon: 'MessageSquare',
    color: 'cyan',
    category: 'ai',
  },
  parallel: {
    type: 'parallel',
    label: '并行执行',
    description: '并行执行多个分支',
    icon: 'GitMerge',
    color: 'indigo',
    category: 'logic',
  },
  api: {
    type: 'api',
    label: 'API调用',
    description: '执行外部 HTTP 请求',
    icon: 'Globe',
    color: 'blue',
    category: 'external',
  },
  classifier: {
    type: 'classifier',
    label: '问题分类器',
    description: '使用LLM对输入进行分类',
    icon: 'LayoutGrid',
    color: 'orange',
    category: 'logic',
  },
};

/**
 * Default node data by type
 */
export const DEFAULT_NODE_DATA: Record<WorkflowNodeType, WorkflowNodeData> = {
  input: {
    type: 'input',
    label: '用户输入',
    input_variables: [{ name: 'query', type: 'string', description: '用户输入的消息内容' }],
  },
  timer: {
    type: 'timer',
    label: '定时触发',
    cron_expression: '0 * * * *',
  },
  webhook: {
    type: 'webhook',
    label: 'Webhook',
    path: '',
    method: 'POST',
  },
  event: {
    type: 'event',
    label: '事件触发',
    event_type: '',
  },
  answer: {
    type: 'answer',
    label: '回复',
    output_type: 'template',
    output_template: '',
  },
  agent: {
    type: 'agent',
    label: 'AI Agent',
    agent_id: '',
  },
  tool: {
    type: 'tool',
    label: 'MCP工具',
    tool_id: '',
  },
  condition: {
    type: 'condition',
    label: '条件判断',
    condition_type: 'expression',
    expression: '',
  },
  llm: {
    type: 'llm',
    label: 'LLM调用',
    user_prompt: '',
    tools: [],
    knowledge_bases: [],
    temperature: 0.7,
    max_tokens: 2000,
  },
  parallel: {
    type: 'parallel',
    label: '并行执行',
    branches: 2,
    wait_for_all: true,
  },
  api: {
    type: 'api',
    label: 'API调用',
    method: 'GET',
    url: '',
    headers: [],
    params: [],
    body_type: 'json',
  },
  classifier: {
    type: 'classifier',
    label: '问题分类器',
    input_variable: '',
    categories: [
      { id: 'cat_1', name: '分类1', description: '描述该分类的触发条件' },
      { id: 'cat_2', name: '分类2', description: '描述该分类的触发条件' },
    ],
  },
};
