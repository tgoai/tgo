import { createBrowserRouter, Navigate } from 'react-router-dom';
import RootLayout from '../components/layout/RootLayout';
import Layout from '../components/layout/Layout';
import ProtectedRoute from '../components/auth/ProtectedRoute';
import ChatPage from '../pages/ChatPage';
import VisitorManagement from '../pages/VisitorManagement';
import AIInterface from '../pages/AIInterface';
import AgentManagement from '../components/ai/AgentManagement';
import Tools from '../components/ai/Tools';
import { DeviceManagement } from '../components/ai/device-control';
import { DeviceDebugChat } from '../components/ai/device-debug';
import WorkflowManagement from '../pages/WorkflowManagement';
import WorkflowEditorPage from '../pages/WorkflowEditorPage';
import LoginPage from '../pages/LoginPage';
import RegisterPage from '../pages/RegisterPage';
import SetupWizard from '../pages/SetupWizard';

import { useTranslation } from 'react-i18next';

// Placeholder component for platforms index that uses i18n
const PlatformPlaceholder: React.FC = () => {
  const { t } = useTranslation();
  return (
    <div className="flex-1 flex items-center justify-center p-6 text-gray-500">
      <div className="text-center">
        <p className="text-sm">{t('channels.placeholder.selectOrCreate', '请选择左侧平台，或点击“＋”创建一个新平台。')}</p>
      </div>
    </div>
  );
};
import KnowledgeBase from '../pages/KnowledgeBase';
import KnowledgeBaseDetail from '../pages/KnowledgeBaseDetail';
import WebsiteKnowledgeBaseDetail from '../pages/WebsiteKnowledgeBaseDetail';
import QAKnowledgeBaseDetail from '../pages/QAKnowledgeBaseDetail';
import PlatformManagement from '../pages/PlatformManagement';
import PlatformConfigPage from '../pages/PlatformConfigPage';
import SettingsLayout from '../pages/SettingsLayout';

import GeneralSettings from '../components/settings/GeneralSettings';
import ProfileSettings from '../components/settings/ProfileSettings';
import StaffSettings from '../components/settings/StaffSettings';
import NotificationSettings from '../components/settings/NotificationSettings';
import ModelProvidersSettings from '../components/settings/ModelProvidersSettings';
import PluginsSettings from '../components/settings/PluginsSettings';
import AboutSettings from '../components/settings/AboutSettings';
import MarkdownTestPage from '../pages/MarkdownTestPage';

// Import SaaS routes if they exist (will be resolved via Vite alias or empty default)
// @ts-ignore
import { saasRoutes } from 'saas-routes';

/**
 * Router configuration for the application
 */
export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      // Setup wizard route (outside of Layout and ProtectedRoute)
      {
        path: 'setup',
        element: <SetupWizard />
      },
      // Authentication routes (outside of Layout)
      {
        path: 'login',
        element: <LoginPage />
      },
      {
        path: 'register',
        element: <RegisterPage />
      },
      // Main application routes
      {
        path: '/',
        element: (
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        ),
        children: [
      {
        index: true,
        element: <Navigate to="/chat" replace />
      },
      {
        path: 'settings',
        element: <SettingsLayout />,
        children: [
          { index: true, element: <Navigate to="/settings/profile" replace /> },

          { path: 'profile', element: <ProfileSettings /> },
          { path: 'general', element: <GeneralSettings /> },
          { path: 'notifications', element: <NotificationSettings /> },
          { path: 'staff', element: <StaffSettings /> },
          { path: 'providers', element: <ModelProvidersSettings /> },
          { path: 'plugins', element: <PluginsSettings /> },
          { path: 'about', element: <AboutSettings /> },
          // Inject SaaS settings routes
          ...(saasRoutes || [])
            .filter((r: any) => r.path.startsWith('/settings/'))
            .map((r: any) => ({
              ...r,
              path: r.path.replace('/settings/', '')
            }))
        ]
      },
      {
        path: 'chat',
        element: <ChatPage />,
        children: [
          { index: true, element: null },
          { path: ':channelType/:channelId', element: null }
        ]
      },
      {
        path: 'visitors',
        element: <VisitorManagement />
      },
      {
        path: 'ai',
        element: <AIInterface />,
        children: [
          {
            index: true,
            element: <Navigate to="/ai/agents" replace />
          },
          {
            path: 'agents',
            element: <AgentManagement />
          },
          {
            path: 'tools',
            element: <Tools />
          },
          {
            path: 'device-control',
            element: <DeviceManagement />
          },
          {
            path: 'device-debug/:deviceId',
            element: <DeviceDebugChat />
          },
          {
            path: 'workflows',
            element: <WorkflowManagement />
          },
          {
            path: 'workflows/:id/edit',
            element: <WorkflowEditorPage />
          },
          {
            path: 'workflows/new',
            element: <WorkflowEditorPage />
          }
        ]
      },
      {
        path: 'knowledge',
        element: <KnowledgeBase/>
      },
      {
        path: 'knowledge/:id',
        element: <KnowledgeBaseDetail/>
      },
      {
        path: 'knowledge/website/:id',
        element: <WebsiteKnowledgeBaseDetail/>
      },
      {
        path: 'knowledge/qa/:id',
        element: <QAKnowledgeBaseDetail/>
      },
      {
        path: 'platforms',
        element: <PlatformManagement />,
        children: [
          {
            index: true,
            element: (
              <PlatformPlaceholder />
            )
          },
          {
            path: ':platformId',
            element: <PlatformConfigPage />
          }
        ]
      },
      {
        path: 'test/markdown',
        element: <MarkdownTestPage />
      },
      // Inject other SaaS routes (that don't go into settings)
      ...(saasRoutes || []).filter((r: any) => !r.path.startsWith('/settings/'))
    ]
      }
    ]
  }
]);
