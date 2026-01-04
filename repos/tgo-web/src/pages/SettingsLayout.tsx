import React from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, NavLink } from 'react-router-dom';
import { Settings as SettingsIcon, Puzzle } from 'lucide-react';
import { FiSettings, FiCpu, FiUsers, FiUser, FiBell } from 'react-icons/fi';
import SettingsSidebar from '@/components/settings/SettingsSidebar';

const SettingsLayout: React.FC = () => {
  const { t } = useTranslation();

  const items: Array<{ id: string; label: string }> = [
    { id: 'profile', label: t('settings.menu.profile', '个人资料') },
    { id: 'general', label: t('settings.menu.general', '通用') },
    { id: 'notifications', label: t('settings.menu.notifications', '消息通知') },
    { id: 'staff', label: t('settings.menu.staff', '人工坐席') },
    { id: 'providers', label: t('settings.menu.providers', '模型提供商') },
    { id: 'plugins', label: t('settings.menu.plugins', '插件管理') },
  ];

  const iconMap: Record<string, React.ReactNode> = {
    profile: <FiUser className="w-4 h-4" />,
    general: <FiSettings className="w-4 h-4" />,
    notifications: <FiBell className="w-4 h-4" />,
    staff: <FiUsers className="w-4 h-4" />,
    providers: <FiCpu className="w-4 h-4" />,
    plugins: <Puzzle className="w-4 h-4" />,
  };

  return (
    <div className="flex-1 flex h-full w-full overflow-hidden bg-gray-50 dark:bg-gray-900">
      <SettingsSidebar />
      <div className="flex-1 overflow-auto">
        <div className="md:hidden bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
          <div className="px-4 py-3">
            <div className="flex items-center gap-2">
              <SettingsIcon className="w-5 h-5 text-gray-700 dark:text-gray-300" />
              <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100">{t('settings.title', '\u8bbe\u7f6e')}</h1>
            </div>
          </div>
          <div className="px-2 pb-2 flex gap-2 overflow-x-auto">
            {items.map((item) => (
              <NavLink
                key={item.id}
                to={`/settings/${item.id}`}
                className={({ isActive }) => `whitespace-nowrap px-3 py-1.5 rounded-md text-sm border ${isActive ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-300 border-blue-200 dark:border-blue-700' : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-200 border-gray-200 dark:border-gray-600'}`}
              >
                <span className="inline-flex items-center gap-1.5">
                  {iconMap[item.id]}
                  <span>{item.label}</span>
                </span>
              </NavLink>
            ))}
          </div>
        </div>
        <Outlet />
      </div>
    </div>
  );
};

export default SettingsLayout;

