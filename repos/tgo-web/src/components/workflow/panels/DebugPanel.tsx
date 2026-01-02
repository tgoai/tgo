/**
 * Debug Panel Component
 * Right-side panel for workflow online running and debugging
 */

import React, { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  X,
  Play,
  StopCircle,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
  ChevronDown,
  Info,
  Terminal,
  History,
  Trash2,
} from 'lucide-react';
import { useWorkflowStore } from '@/stores/workflowStore';

const DebugPanel: React.FC = () => {
  const { t } = useTranslation();
  const {
    currentWorkflow,
    isExecuting,
    executionError,
    currentExecution,
    nodeExecutionMap,
    setDebugPanelOpen,
    startExecution,
    cancelExecution,
    clearExecution,
    debugInput,
    setDebugInput,
  } = useWorkflowStore();

  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

  const nodes = currentWorkflow?.definition?.nodes || [];
  
  // Find all input nodes and their variables
  const inputNodes = useMemo(() => {
    return nodes.filter(n => n.type === 'input');
  }, [nodes]);

  const inputVariables = useMemo(() => {
    const vars: { name: string; type: string; description?: string; nodeId: string }[] = [];
    inputNodes.forEach(node => {
      const data = node.data as any;
      if (data.input_variables && Array.isArray(data.input_variables)) {
        data.input_variables.forEach((v: any) => {
          vars.push({ ...v, nodeId: node.id });
        });
      }
    });
    return vars;
  }, [inputNodes]);

  // Handle input changes
  const handleInputChange = (name: string, value: string, type: string) => {
    let typedValue: any = value;
    if (type === 'number') {
      typedValue = value === '' ? '' : Number(value);
    } else if (type === 'boolean') {
      typedValue = value === 'true';
    }
    setDebugInput({ ...debugInput, [name]: typedValue });
  };

  const handleRun = () => {
    startExecution(debugInput);
  };

  const handleCancel = () => {
    cancelExecution();
  };

  const handleClear = () => {
    clearExecution();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-300" />;
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'running': return t('workflow.debug.running', '正在运行...');
      case 'completed': return t('workflow.debug.success', '执行成功');
      case 'failed': return t('workflow.debug.failed', '执行失败');
      case 'pending': return t('workflow.debug.pending', '等待中');
      default: return status;
    }
  };

  // Sort nodes by execution time if available, or maintain a logical order
  const executedNodes = useMemo(() => {
    // If we have a map of executions (live updates), use it
    if (Object.keys(nodeExecutionMap).length > 0) {
      return Object.values(nodeExecutionMap).sort((a, b) => 
        new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
      );
    }
    // Fallback to static node_executions if available (historical or final state)
    if (!currentExecution?.node_executions) return [];
    return [...currentExecution.node_executions].sort((a, b) => 
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
    );
  }, [currentExecution, nodeExecutionMap]);

  const toggleNodeExpand = (nodeId: string) => {
    setExpandedNodes(prev => ({ ...prev, [nodeId]: !prev[nodeId] }));
  };

  return (
    <div className="w-80 bg-white dark:bg-gray-900 border-l border-gray-100 dark:border-gray-800 flex flex-col z-20 shadow-2xl transition-all animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="px-6 py-5 border-b border-gray-50 dark:border-gray-800 flex items-center justify-between bg-white/80 dark:bg-gray-900/80 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400">
            <Terminal className="w-5 h-5" />
          </div>
          <div>
            <h3 className="font-bold text-gray-900 dark:text-gray-100 text-sm">{t('workflow.debug.title', '在线调试')}</h3>
            <p className="text-[10px] text-gray-400 font-medium uppercase tracking-wider">Debug Mode</p>
          </div>
        </div>
        <button
          onClick={() => setDebugPanelOpen(false)}
          className="p-2 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl transition-colors text-gray-400 hover:text-gray-600"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <div className="p-6 space-y-8">
          {/* Input Variables Section */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-gray-400" />
                <h4 className="text-[11px] uppercase font-bold text-gray-400 tracking-wider">{t('workflow.debug.input_variables', '输入变量')}</h4>
              </div>
              {inputVariables.length > 0 && (
                <button 
                  onClick={() => setDebugInput({})}
                  className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors"
                >
                  {t('workflow.debug.reset', '重置')}
                </button>
              )}
            </div>

            {inputVariables.length > 0 ? (
              <div className="space-y-4">
                {inputVariables.map((v) => (
                  <div key={`${v.nodeId}-${v.name}`} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-bold text-gray-700 dark:text-gray-300">
                        {v.name}
                      </label>
                      <span className="text-[10px] text-gray-400 font-mono">{v.type}</span>
                    </div>
                    {v.description && (
                      <p className="text-[10px] text-gray-400 leading-relaxed">
                        {v.description}
                      </p>
                    )}
                    {v.type === 'boolean' ? (
                      <select
                        value={String(debugInput[v.name] ?? 'false')}
                        onChange={(e) => handleInputChange(v.name, e.target.value, v.type)}
                        className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-sm dark:text-gray-100 cursor-pointer"
                        disabled={isExecuting}
                      >
                        <option value="true">True</option>
                        <option value="false">False</option>
                      </select>
                    ) : (
                      <input
                        type={v.type === 'number' ? 'number' : 'text'}
                        value={debugInput[v.name] ?? ''}
                        onChange={(e) => handleInputChange(v.name, e.target.value, v.type)}
                        className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-800/50 border border-gray-100 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all text-sm dark:text-gray-100"
                        placeholder={`请输入 ${v.name}...`}
                        disabled={isExecuting}
                      />
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-dashed border-gray-200 dark:border-gray-700">
                <p className="text-xs text-gray-400 text-center">{t('workflow.debug.no_input_variables', '无输入变量')}</p>
              </div>
            )}

            <div className="pt-2 flex gap-2">
              {!isExecuting ? (
                <button
                  onClick={handleRun}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-sm transition-all shadow-lg shadow-blue-500/20 active:scale-95"
                >
                  <Play className="w-4 h-4 fill-current" />
                  {t('workflow.debug.run', '运行工作流')}
                </button>
              ) : (
                <button
                  onClick={handleCancel}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl font-bold text-sm transition-all hover:bg-red-100 dark:hover:bg-red-900/30 active:scale-95"
                >
                  <StopCircle className="w-4 h-4" />
                  {t('workflow.debug.stop', '停止运行')}
                </button>
              )}
            </div>
          </section>

          {/* Execution Status Section */}
          {(currentExecution || isExecuting || executionError) && (
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <History className="w-4 h-4 text-gray-400" />
                  <h4 className="text-[11px] uppercase font-bold text-gray-400 tracking-wider">{t('workflow.debug.execution_status', '执行状态')}</h4>
                </div>
                {!isExecuting && (
                  <button 
                    onClick={handleClear}
                    className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors text-gray-400 hover:text-red-500"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              <div className="bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-100 dark:border-gray-700 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {currentExecution ? getStatusIcon(currentExecution.status) : <Loader2 className="w-4 h-4 animate-spin text-blue-500" />}
                    <span className="text-xs font-bold text-gray-700 dark:text-gray-200 capitalize">
                      {currentExecution ? getStatusText(currentExecution.status) : t('workflow.debug.starting', '启动中...')}
                    </span>
                  </div>
                  {currentExecution?.duration && (
                    <span className="text-[10px] text-gray-400 font-mono">
                      {(currentExecution.duration / 1000).toFixed(2)}s
                    </span>
                  )}
                </div>

                {executionError && (
                  <div className="p-4 bg-red-50 dark:bg-red-900/10 text-red-600 dark:text-red-400 text-[11px] leading-relaxed">
                    <p className="font-bold mb-1 flex items-center gap-1">
                      <XCircle className="w-3 h-3" />
                      {t('workflow.debug.error', '执行错误')}
                    </p>
                    {executionError}
                  </div>
                )}

                {/* Timeline */}
                <div className="p-4 space-y-4">
                  {executedNodes.length > 0 ? (
                    <div className="space-y-3 relative before:absolute before:left-[7px] before:top-2 before:bottom-2 before:w-[1px] before:bg-gray-200 dark:before:bg-gray-700">
                      {executedNodes.map((ne) => (
                        <div key={ne.id} className="relative pl-6">
                          <div className="absolute left-0 top-1.5 w-3.5 h-3.5 rounded-full bg-white dark:bg-gray-900 flex items-center justify-center z-10">
                            {getStatusIcon(ne.status)}
                          </div>
                          <div className="group">
                            <div 
                              className="flex items-center justify-between cursor-pointer"
                              onClick={() => toggleNodeExpand(ne.node_id)}
                            >
                              <span className="text-xs font-medium text-gray-700 dark:text-gray-200 group-hover:text-blue-500 transition-colors">
                                {nodes.find(n => n.id === ne.node_id)?.data.label || ne.node_type}
                              </span>
                              <div className="flex items-center gap-2">
                                {ne.duration !== undefined && ne.duration !== null && (
                                  <span className="text-[9px] text-gray-400 font-mono">
                                    {ne.duration < 1000 ? `${ne.duration}ms` : `${(ne.duration / 1000).toFixed(1)}s`}
                                  </span>
                                )}
                                {expandedNodes[ne.node_id] ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />}
                              </div>
                            </div>
                            
                            {expandedNodes[ne.node_id] && (
                              <div 
                                className="mt-2 space-y-2 animate-in fade-in slide-in-from-top-1 duration-200"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {ne.input && (
                                  <div className="space-y-1">
                                    <span className="text-[9px] text-gray-400 font-bold uppercase tracking-wider">Input</span>
                                    <pre className="p-2 bg-gray-900 dark:bg-black rounded-lg text-[10px] text-blue-400 overflow-x-auto font-mono">
                                      {JSON.stringify(ne.input, null, 2)}
                                    </pre>
                                  </div>
                                )}
                                {ne.output && (
                                  <div className="space-y-1">
                                    <span className="text-[9px] text-gray-400 font-bold uppercase tracking-wider">Output</span>
                                    <pre className="p-2 bg-gray-900 dark:bg-black rounded-lg text-[10px] text-green-400 overflow-x-auto font-mono">
                                      {JSON.stringify(ne.output, null, 2)}
                                    </pre>
                                  </div>
                                )}
                                {ne.error && (
                                  <div className="space-y-1">
                                    <span className="text-[9px] text-red-400 font-bold uppercase tracking-wider">Error</span>
                                    <div className="p-2 bg-red-50 dark:bg-red-900/20 rounded-lg text-[10px] text-red-600 dark:text-red-400 font-mono">
                                      {ne.error}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 opacity-50">
                      <Terminal className="w-8 h-8 text-gray-300 mb-2" />
                      <p className="text-[10px] text-gray-400 font-medium">{t('workflow.debug.waiting', '等待执行...')}</p>
                    </div>
                  )}
                </div>
              </div>
            </section>
          )}

          {/* Final Output Section */}
          {currentExecution?.output && (
            <section className="space-y-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <h4 className="text-[11px] uppercase font-bold text-gray-400 tracking-wider">{t('workflow.debug.final_output', '最终输出')}</h4>
              </div>
              <div className="p-4 bg-green-50/50 dark:bg-green-900/10 rounded-2xl border border-green-100 dark:border-green-900/30">
                <pre className="text-xs text-green-700 dark:text-green-400 whitespace-pre-wrap font-mono leading-relaxed">
                  {JSON.stringify(currentExecution.output, null, 2)}
                </pre>
              </div>
            </section>
          )}
        </div>
      </div>

      {/* Persistence Note */}
      <div className="p-4 bg-blue-50/30 dark:bg-blue-900/5 border-t border-gray-50 dark:border-gray-800">
        <div className="flex items-start gap-2">
          <Info className="w-3 h-3 text-blue-500 mt-0.5" />
          <p className="text-[9px] text-gray-400 leading-relaxed">
            {t('workflow.debug.persistence_note', '调试模式下的执行结果仅供预览，不会影响线上运行的工作流版本。')}
          </p>
        </div>
      </div>
    </div>
  );
};

export default DebugPanel;

