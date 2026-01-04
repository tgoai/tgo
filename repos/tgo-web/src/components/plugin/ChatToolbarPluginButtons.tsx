import React, { useEffect } from 'react';
import * as LucideIcons from 'lucide-react';
import { Puzzle } from 'lucide-react';
import { usePluginStore } from '@/stores/pluginStore';
import { useTranslation } from 'react-i18next';

interface ChatToolbarPluginButtonsProps {
  context: any;
  disabled?: boolean;
}

const ChatToolbarPluginButtons: React.FC<ChatToolbarPluginButtonsProps> = ({ context, disabled }) => {
  const { t } = useTranslation();
  const toolbarButtons = usePluginStore((state) => state.toolbarButtons);
  const fetchToolbarButtons = usePluginStore((state) => state.fetchToolbarButtons);
  const openPluginModal = usePluginStore((state) => state.openPluginModal);

  useEffect(() => {
    fetchToolbarButtons();
  }, [fetchToolbarButtons]);

  const renderIcon = (iconName?: string) => {
    if (!iconName) return <Puzzle className="w-6 h-6" />;
    
    // Convert crown -> Crown, external-link -> ExternalLink
    const pascalName = iconName
      .split(/[-_]/)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
      
    const Icon = (LucideIcons as any)[pascalName] || (LucideIcons as any)[iconName];
    if (!Icon) return <Puzzle className="w-6 h-6" />;
    return <Icon className="w-6 h-6" />;
  };

  if (toolbarButtons.length === 0) return null;

  return (
    <>
      {toolbarButtons.map((btn) => (
        <button
          key={btn.plugin_id}
          onClick={() => !disabled && openPluginModal(btn.plugin_id, btn.title, { ...context, is_modal: true })}
          disabled={disabled}
          className="p-1.5 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label={btn.title}
          title={disabled ? t('chat.input.disabled.tooltip', 'AI助手已启用，手动输入已禁用') : (btn.tooltip || btn.title)}
        >
          {renderIcon(btn.icon)}
        </button>
      ))}
    </>
  );
};

export default ChatToolbarPluginButtons;

