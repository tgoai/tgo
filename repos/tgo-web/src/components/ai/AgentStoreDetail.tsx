import React from 'react';
import { X, Bot, ShieldCheck, Check, Plus, Loader2, Users } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { AgentStoreItem } from '@/types';

interface AgentStoreDetailProps {
  agent: AgentStoreItem | null;
  isOpen: boolean;
  onClose: () => void;
  onInstall: (agent: AgentStoreItem) => void;
  isInstalled: boolean;
  installingId: string | null;
}

const AgentStoreDetail: React.FC<AgentStoreDetailProps> = ({ 
  agent, 
  isOpen, 
  onClose, 
  onInstall, 
  isInstalled,
  installingId
}) => {
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language.startsWith('zh') ? 'zh' : 'en';

  if (!agent) return null;

  const title = currentLang === 'zh' 
    ? (agent.title_zh || agent.name) 
    : (agent.title_en || agent.title_zh || agent.name);
  
  const description = currentLang === 'zh'
    ? agent.description_zh
    : (agent.description_en || agent.description_zh);

  return (
    <div className={`fixed inset-y-0 right-0 z-[60] w-full max-w-2xl bg-white dark:bg-gray-900 shadow-2xl transform transition-transform duration-500 ease-in-out ${isOpen ? 'translate-x-0' : 'translate-x-full'}`}>
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="px-8 py-6 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
          <h2 className="text-xl font-black text-gray-900 dark:text-gray-100">{t('modelDetail.details', '详细信息')}</h2>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl text-gray-400 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          <div className="flex items-start gap-6 mb-10">
            <div className="w-24 h-24 rounded-[2rem] bg-indigo-50 dark:bg-indigo-900/20 flex items-center justify-center text-5xl border border-indigo-100 dark:border-indigo-800 overflow-hidden">
              {agent.avatar_url ? (
                <img src={agent.avatar_url} alt={title} className="w-full h-full object-cover" />
              ) : (
                <Bot className="w-12 h-12 text-indigo-600 dark:text-indigo-400" />
              )}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <h1 className="text-3xl font-black text-gray-900 dark:text-gray-100 tracking-tight">{title}</h1>
                <ShieldCheck className="w-6 h-6 text-blue-500" />
              </div>
              <div className="flex flex-wrap gap-2 mb-4">
                {agent.tags?.map(tag => (
                  <span key={tag} className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-500 text-[10px] font-black uppercase tracking-wider rounded-lg">
                    {tag}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-6 text-sm font-bold text-gray-400">
                <div className="flex items-center gap-1.5">
                  <span className="text-gray-900 dark:text-gray-100">${Number(agent.price).toFixed(2)}</span>
                  <span className="uppercase tracking-widest text-[9px]">/ HIRE</span>
                </div>
                <div className="w-1.5 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full" />
                <div className="flex items-center gap-1.5">
                  <Users className="w-4 h-4" />
                  <span>850+ Users</span>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-10">
            <section>
              <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em] mb-4">{t('modelDetail.intro', '员工介绍')}</h3>
              <p className="text-gray-600 dark:text-gray-400 leading-relaxed font-medium">
                {description || '暂无详细描述'}
              </p>
            </section>

            <section>
              <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em] mb-4">技能配置</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-100 dark:border-gray-800">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">推荐模型</p>
                  <p className="font-bold text-gray-900 dark:text-gray-100">{agent.model?.title_zh || agent.model?.name || '通用模型'}</p>
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-2xl border border-gray-100 dark:border-gray-800">
                  <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1">工具数量</p>
                  <p className="font-bold text-gray-900 dark:text-gray-100">{agent.recommended_tools?.length || 0} 个预装工具</p>
                </div>
              </div>
            </section>

            <section>
              <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em] mb-4">系统提示词预览</h3>
              <div className="p-6 bg-gray-900 text-gray-300 rounded-3xl font-mono text-xs leading-relaxed border border-white/5 shadow-inner italic">
                "{agent.instruction.substring(0, 200)}..."
              </div>
            </section>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-8 border-t border-gray-100 dark:border-gray-800 bg-gray-50/50 dark:bg-gray-900/50">
          <button
            onClick={() => onInstall(agent)}
            disabled={isInstalled || installingId === agent.id}
            className={`w-full py-4 rounded-2xl text-sm font-black uppercase tracking-widest transition-all flex items-center justify-center gap-3 shadow-xl ${
              isInstalled 
                ? 'bg-green-500 text-white cursor-not-allowed' 
                : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-indigo-500/20 active:scale-[0.98]'
            }`}
          >
            {isInstalled ? (
              <>
                <Check className="w-5 h-5" />
                {t('common.installed', '已在团队中')}
              </>
            ) : installingId === agent.id ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                招聘中...
              </>
            ) : (
              <>
                <Plus className="w-5 h-5" />
                {t('agents.store.hireNow', '立即招聘')}
              </>
            )}
          </button>
          <p className="text-center text-[10px] text-gray-400 font-bold uppercase tracking-widest mt-4">
            招聘后该员工将立即出现在您的 AI 员工列表中
          </p>
        </div>
      </div>
    </div>
  );
};

export default AgentStoreDetail;
