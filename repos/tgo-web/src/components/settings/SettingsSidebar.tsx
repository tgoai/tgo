import React from 'react';
import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Settings as SettingsIcon, Puzzle } from 'lucide-react';
import { FiSettings, FiCpu, FiInfo, FiLogOut, FiUsers, FiUser, FiBell } from 'react-icons/fi';
import { useAuthStore } from '@/stores/authStore';
import OnboardingSidebarPanel from '@/components/onboarding/OnboardingSidebarPanel';

interface SettingsSidebarProps {
  className?: string;
}

const SettingsSidebar: React.FC<SettingsSidebarProps> = ({ className = '' }) => {
  const { t } = useTranslation();
  const { logout, isAuthenticated, user } = useAuthStore();
  const isAdmin = user?.role === 'admin';

  const allItems: Array<{ id: string; label: string }> = [
    { id: 'profile', label: t('settings.menu.profile', '个人资料') },
    { id: 'general', label: t('settings.menu.general', '通用') },
    { id: 'notifications', label: t('settings.menu.notifications', '消息通知') },
    { id: 'staff', label: t('settings.menu.staff', '人工坐席') },
    { id: 'providers', label: t('settings.menu.providers', '模型提供商') },
    { id: 'plugins', label: t('settings.menu.plugins', '插件管理') },
  ];

  // Filter settings items based on user role
  // Non-admin users cannot see 'staff' (人工坐席), 'providers' (模型提供商) and 'plugins' (插件管理)
  const items = allItems.filter(item => {
    if (!isAdmin && (item.id === 'staff' || item.id === 'providers' || item.id === 'plugins')) {
      return false;
    }
    return true;
  });

  const iconMap: Record<string, React.ReactNode> = {
    profile: <FiUser className="w-4 h-4" />,
    general: <FiSettings className="w-4 h-4" />,
    notifications: <FiBell className="w-4 h-4" />,
    staff: <FiUsers className="w-4 h-4" />,
    providers: <FiCpu className="w-4 h-4" />,
    plugins: <Puzzle className="w-4 h-4" />,
  };

  return (
    <aside className={`hidden md:flex w-64 flex-col bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 shrink-0 ${className}`}>
      <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <SettingsIcon className="w-4 h-4 text-gray-700 dark:text-gray-300" />
          <h2 className="text-base font-semibold text-gray-800 dark:text-gray-100">{t('settings.title', '设置')}</h2>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto p-2 space-y-1">
        {items.map((item) => (
          <NavLink
            key={item.id}
            to={`/settings/${item.id}`}
            className={({ isActive }) => `
              block px-3 py-2 rounded-md text-sm transition-colors
              ${isActive ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'}
            `}
          >
            <span className="inline-flex items-center gap-2">
              {iconMap[item.id]}
              <span>{item.label}</span>
            </span>
          </NavLink>
        ))}
      </nav>
      <div className="p-2 border-t border-gray-200 dark:border-gray-700 space-y-1">
        <NavLink
          to="/settings/about"
          className={({ isActive }) => `
            block px-3 py-2 rounded-md text-sm transition-colors
            ${isActive ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400' : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'}
          `}
        >
          <span className="inline-flex items-center gap-2">
            <FiInfo className="w-4 h-4" />
            <span>{t('settings.menu.about', '关于')}</span>
          </span>
        </NavLink>
        {isAuthenticated && (
          <button
            onClick={async () => {
              try {
                await logout();
              } catch (error) {
                console.error('Logout failed:', error);
              }
            }}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
          >
            <FiLogOut className="w-4 h-4" />
            <span>{t('settings.menu.logout', '退出登录')}</span>
          </button>
        )}
      </div>

      {/* Onboarding Panel */}
      <OnboardingSidebarPanel />
    </aside>
  );
};

export default SettingsSidebar;
