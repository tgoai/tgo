import React, { useState, useEffect } from 'react';
import { X, Loader2, CheckCircle2, AlertCircle, Wrench, Cpu, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { AgentDependencyCheckResponse } from '@/types';

interface AgentDependencyModalProps {
  isOpen: boolean;
  onClose: () => void;
  dependencyData: AgentDependencyCheckResponse | null;
  onConfirm: (selectedToolIds: string[], installModel: boolean) => void;
  isInstalling: boolean;
}

const AgentDependencyModal: React.FC<AgentDependencyModalProps> = ({
  isOpen,
  onClose,
  dependencyData,
  onConfirm,
  isInstalling
}) => {
  const { i18n } = useTranslation();
  const currentLang = i18n.language.startsWith('zh') ? 'zh' : 'en';
  
  const [selectedTools, setSelectedTools] = useState<string[]>([]);
  const [installModel, setInstallModel] = useState(true);

  useEffect(() => {
    if (dependencyData) {
      setSelectedTools(dependencyData.missing_tools.map(t => t.id));
      setInstallModel(!!dependencyData.missing_model);
    }
  }, [dependencyData]);

  if (!dependencyData) return null;

  const { agent, missing_tools, missing_model } = dependencyData;
  const agentName = currentLang === 'zh' ? agent.title_zh : (agent.title_en || agent.name);

  const toggleTool = (id: string) => {
    setSelectedTools(prev => 
      prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]
    );
  };

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6">
          <div 
            className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm animate-in fade-in duration-300"
            onClick={!isInstalling ? onClose : undefined}
          />

          <div className="relative w-full max-w-lg bg-white dark:bg-gray-900 rounded-[2.5rem] shadow-2xl overflow-hidden border border-gray-100 dark:border-gray-800 animate-in zoom-in-95 slide-in-from-bottom-8 duration-500">
            {/* Header */}
            <div className="h-32 bg-gradient-to-br from-indigo-600 to-blue-700 relative overflow-hidden">
              <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-20"></div>
              
              {!isInstalling && (
                <button 
                  onClick={onClose}
                  className="absolute top-4 right-4 p-2 bg-black/10 hover:bg-black/20 text-white rounded-full transition-colors z-10"
                >
                  <X className="w-4 h-4" />
                </button>
              )}

              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-16 h-16 bg-white dark:bg-gray-800 rounded-2xl shadow-xl flex items-center justify-center text-indigo-600">
                  <ShieldCheck className="w-8 h-8" />
                </div>
              </div>
            </div>

            <div className="p-8 space-y-6">
              <div className="text-center space-y-2">
                <h2 className="text-2xl font-black text-gray-900 dark:text-gray-100 tracking-tight">
                  招聘准备
                </h2>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  正在为 <span className="font-bold text-indigo-600 dark:text-indigo-400">{agentName}</span> 安装必要的依赖环境
                </p>
              </div>

              <div className="space-y-4">
                {/* Tools Section */}
                {missing_tools.length > 0 && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-xs font-black text-gray-400 uppercase tracking-widest">
                      <Wrench className="w-3 h-3" />
                      需安装的工具 ({missing_tools.length})
                    </div>
                    <div className="bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-100 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-800">
                      {missing_tools.map(tool => (
                        <div 
                          key={tool.id}
                          onClick={() => !isInstalling && toggleTool(tool.id)}
                          className={`flex items-center gap-3 p-4 transition-colors ${!isInstalling ? 'cursor-pointer hover:bg-gray-100/50 dark:hover:bg-gray-800' : ''}`}
                        >
                          <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all ${
                            selectedTools.includes(tool.id)
                              ? 'bg-indigo-600 border-indigo-600 text-white'
                              : 'border-gray-300 dark:border-gray-600'
                          }`}>
                            {selectedTools.includes(tool.id) && <CheckCircle2 className="w-3.5 h-3.5" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-bold text-gray-900 dark:text-gray-100 truncate">
                              {tool.title_zh || tool.name}
                            </p>
                            <p className="text-[10px] text-gray-500 font-medium">
                              单次调用: ¥{tool.price_per_call.toFixed(2)}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Model Section */}
                {missing_model && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-xs font-black text-gray-400 uppercase tracking-widest">
                      <Cpu className="w-3 h-3" />
                      需绑定的模型
                    </div>
                    <div 
                      onClick={() => !isInstalling && setInstallModel(!installModel)}
                      className={`bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-100 dark:border-gray-800 p-4 flex items-center gap-3 transition-colors ${!isInstalling ? 'cursor-pointer hover:bg-gray-100/50 dark:hover:bg-gray-800' : ''}`}
                    >
                      <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all ${
                        installModel
                          ? 'bg-indigo-600 border-indigo-600 text-white'
                          : 'border-gray-300 dark:border-gray-600'
                      }`}>
                        {installModel && <CheckCircle2 className="w-3.5 h-3.5" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-gray-900 dark:text-gray-100 truncate">
                          {missing_model.title_zh || missing_model.name}
                        </p>
                        <p className="text-[10px] text-gray-500 font-medium">
                          提供商: {missing_model.provider.name}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <div className="bg-amber-50 dark:bg-amber-900/20 p-4 rounded-2xl border border-amber-100/50 dark:border-amber-800/30 flex gap-3">
                  <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
                  <p className="text-xs font-bold text-amber-700 dark:text-amber-300 leading-relaxed">
                    确认后系统将自动为您安装选中的工具和模型，并最终完成员工招聘。
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                {!isInstalling && (
                  <button
                    onClick={onClose}
                    className="flex-1 py-4 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400 font-black rounded-2xl transition-all active:scale-[0.98]"
                  >
                    取消
                  </button>
                )}
                <button
                  onClick={() => onConfirm(selectedTools, installModel)}
                  disabled={isInstalling || (selectedTools.length === 0 && !installModel && missing_tools.length > 0)}
                  className="flex-[2] py-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-black rounded-2xl shadow-xl shadow-indigo-200 dark:shadow-none transition-all active:scale-[0.98] flex items-center justify-center gap-2"
                >
                  {isInstalling ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      安装并招聘中...
                    </>
                  ) : (
                    '确认招聘'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default AgentDependencyModal;
