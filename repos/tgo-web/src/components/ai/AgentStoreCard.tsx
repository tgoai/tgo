import React from 'react';
import { ShieldCheck, Bot } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { AgentStoreItem } from '@/types';

interface AgentStoreCardProps {
  agent: AgentStoreItem;
  onClick: (agent: AgentStoreItem) => void;
  onInstall: (e: React.MouseEvent, agent: AgentStoreItem) => void;
  isInstalled?: boolean;
}

const AgentStoreCard: React.FC<AgentStoreCardProps> = ({ agent, onClick, onInstall, isInstalled }) => {
  const { t, i18n } = useTranslation();
  const currentLang = i18n.language.startsWith('zh') ? 'zh' : 'en';

  const title = currentLang === 'zh' 
    ? (agent.title_zh || agent.name) 
    : (agent.title_en || agent.title_zh || agent.name);
  
  const description = currentLang === 'zh'
    ? agent.description_zh
    : (agent.description_en || agent.description_zh);

  return (
    <div 
      onClick={() => onClick(agent)}
      className="group relative bg-white dark:bg-gray-800 rounded-2xl p-5 border border-gray-100 dark:border-gray-700 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 cursor-pointer overflow-hidden"
    >
      <div className="flex items-start gap-4 mb-4">
        {/* Avatar */}
        <div className="w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-900/20 flex items-center justify-center text-3xl border border-indigo-100 dark:border-indigo-800 group-hover:scale-110 transition-transform duration-300 overflow-hidden">
          {agent.avatar_url ? (
            <img src={agent.avatar_url} alt={title} className="w-full h-full object-cover" />
          ) : (
            <Bot className="w-8 h-8 text-indigo-600 dark:text-indigo-400" />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <h3 className="font-bold text-gray-900 dark:text-gray-100 truncate group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
              {title}
            </h3>
            <ShieldCheck className="w-4 h-4 text-indigo-500 flex-shrink-0" />
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 font-medium flex items-center justify-between">
            <span className="truncate pr-2">{agent.model?.name || 'GPT-4o'}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-black uppercase tracking-wider flex-shrink-0 ${
              (agent.price || 0) > 0 
                ? 'bg-orange-50 text-orange-600 dark:bg-orange-900/20 dark:text-orange-400' 
                : 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400'
            }`}>
              {(agent.price || 0) > 0 ? `$${agent.price}` : t('tools.store.free', '免费')}
            </span>
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 h-10 mb-4 leading-relaxed">
        {description || '暂无描述'}
      </p>

      {/* Footer / Actions */}
      <div className="flex items-center justify-between gap-3 pt-4 border-t border-gray-50 dark:border-gray-700/50">
        <div className="flex flex-wrap gap-1 items-center">
          {agent.tags && agent.tags.slice(0, 2).map(tag => (
            <span 
              key={tag} 
              className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-[10px] rounded-md font-medium"
            >
              {tag}
            </span>
          ))}
        </div>

        <button
          onClick={(e) => onInstall(e, agent)}
          disabled={isInstalled}
          className={`px-4 py-1.5 rounded-xl text-xs font-bold transition-all active:scale-95 ${
            isInstalled 
              ? 'bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed' 
              : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-lg shadow-indigo-200 dark:shadow-none'
          }`}
        >
          {isInstalled ? t('common.installed', '已安装') : t('agents.store.hire', '招聘')}
        </button>
      </div>
    </div>
  );
};

export default AgentStoreCard;
