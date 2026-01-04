import React from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import * as LucideIcons from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/hooks/useToast';

interface KeyValueItem {
  label: string;
  value: any;
  icon?: string;
  color?: string;
  type?: 'text' | 'link' | 'status';
  copyable?: boolean;
  link?: string;
}

interface KeyValueTemplateProps {
  title?: string;
  items: KeyValueItem[];
}

const KeyValueTemplate: React.FC<KeyValueTemplateProps> = ({ title, items }) => {
  const { t } = useTranslation();
  const { showToast } = useToast();

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    showToast('success', t('common.copySuccess', '复制成功'), text);
  };

  const renderIcon = (iconName?: string, color?: string) => {
    if (!iconName) return null;
    
    // Convert crown -> Crown, external-link -> ExternalLink
    const pascalName = iconName
      .split(/[-_]/)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
      
    const Icon = (LucideIcons as any)[pascalName] || (LucideIcons as any)[iconName];
    if (!Icon) return null;
    return <Icon size={14} className="mr-1.5" style={{ color }} />;
  };

  const renderValue = (item: KeyValueItem) => {
    if (item.type === 'link') {
      return (
        <a
          href={item.link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 hover:underline flex items-center"
        >
          {item.value}
          <ExternalLink size={12} className="ml-1" />
        </a>
      );
    }

    if (item.color) {
      return (
        <span
          className="px-2 py-0.5 rounded-full text-[10px] font-medium"
          style={{
            backgroundColor: `${item.color}20`,
            color: item.color,
          }}
        >
          {item.value}
        </span>
      );
    }

    return <span>{item.value}</span>;
  };

  return (
    <div className="space-y-3">
      {title && (
        <h5 className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
          {title}
        </h5>
      )}
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-100 dark:border-gray-700 overflow-hidden">
        <dl className="divide-y divide-gray-100 dark:divide-gray-700">
          {items.map((item, index) => (
            <div key={index} className="flex items-center justify-between p-3 text-sm">
              <dt className="text-gray-500 dark:text-gray-400 flex items-center">
                {renderIcon(item.icon, item.color)}
                {item.label}
              </dt>
              <dd className="text-gray-900 dark:text-gray-100 font-medium flex items-center">
                {renderValue(item)}
                {item.copyable && (
                  <button
                    onClick={() => handleCopy(String(item.value))}
                    className="ml-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
                    title={t('common.copy', '复制')}
                  >
                    <Copy size={12} />
                  </button>
                )}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
};

export default KeyValueTemplate;

