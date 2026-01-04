import React from 'react';
import * as LucideIcons from 'lucide-react';

interface ButtonTemplateProps {
  label: string;
  action_id: string;
  type?: 'primary' | 'secondary' | 'danger' | 'link';
  icon?: string;
  disabled?: boolean;
  onClick: (actionId: string) => void;
}

const ButtonTemplate: React.FC<ButtonTemplateProps> = ({
  label,
  action_id,
  type = 'primary',
  icon,
  disabled,
  onClick,
}) => {
  const renderIcon = () => {
    if (!icon) return null;
    
    // Convert crown -> Crown, external-link -> ExternalLink
    const pascalName = icon
      .split(/[-_]/)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
      
    const Icon = (LucideIcons as any)[pascalName] || (LucideIcons as any)[icon];
    if (!Icon) return null;
    return <Icon size={14} className="mr-1.5" />;
  };

  const baseClasses = "inline-flex items-center justify-center px-3 py-1.5 text-sm font-medium rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed";
  
  const typeClasses = {
    primary: "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500",
    secondary: "bg-gray-100 text-gray-700 hover:bg-gray-200 focus:ring-gray-500 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600",
    danger: "bg-red-600 text-white hover:bg-red-700 focus:ring-red-500",
    link: "bg-transparent text-blue-600 hover:underline px-0 py-0 h-auto focus:ring-0",
  };

  return (
    <button
      onClick={() => onClick(action_id)}
      disabled={disabled}
      className={`${baseClasses} ${typeClasses[type] || typeClasses.primary}`}
    >
      {renderIcon()}
      {label}
    </button>
  );
};

export default ButtonTemplate;

