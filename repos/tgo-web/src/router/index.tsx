import { createBrowserRouter, Navigate } from 'react-router-dom';
import RootLayout from '../components/layout/RootLayout';
import Layout from '../components/layout/Layout';
import ProtectedRoute from '../components/auth/ProtectedRoute';
import ChatPage from '../pages/ChatPage';
import AIInterface from '../pages/AIInterface';
import AgentManagement from '../components/ai/AgentManagement';
import MCPTools from '../components/ai/MCPTools';
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
import PlatformManagement from '../pages/PlatformManagement';
import PlatformConfigPage from '../pages/PlatformConfigPage';
import SettingsLayout from '../pages/SettingsLayout';

import GeneralSettings from '../components/settings/GeneralSettings';

import ModelProvidersSettings from '../components/settings/ModelProvidersSettings';
import AboutSettings from '../components/settings/AboutSettings';
import MarkdownTestPage from '../pages/MarkdownTestPage';

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
          { index: true, element: <Navigate to="/settings/general" replace /> },

          { path: 'general', element: <GeneralSettings /> },

          { path: 'providers', element: <ModelProvidersSettings /> },
          { path: 'about', element: <AboutSettings /> }
        ]
      },
      {
        path: 'chat',
        element: <ChatPage />
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
            path: 'mcp-tools',
            element: <MCPTools />
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
      }
    ]
      }
    ]
  }
]);
