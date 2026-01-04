import React, { useEffect, useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useSetupStore } from '@/stores/setupStore';
import PluginModal from '../plugin/PluginModal';
import { useToast } from '@/hooks/useToast';

/**
 * RootLayout Component
 * 
 * Wraps all routes and checks if the system installation is complete.
 * If installation is not complete, redirects to the setup wizard.
 * 
 * This component is rendered inside the RouterProvider, so it has access
 * to React Router hooks like useNavigate() and useLocation().
 */
const RootLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { isInstalled, isChecking, checkError, checkSetupStatus } = useSetupStore();
  const [isInitializing, setIsInitializing] = useState(true);
  const { showToast } = useToast();

  // Listen for plugin toast events
  useEffect(() => {
    const handlePluginToast = (e: any) => {
      const { message, type } = e.detail;
      // Use the stable showToast from the context, but since we are in RootLayout
      // we can call it directly. showToast from useToast might be unstable.
      showToast(type || 'success', 'Plugin', message);
    };
    window.addEventListener('tgo:show_toast', handlePluginToast);
    return () => window.removeEventListener('tgo:show_toast', handlePluginToast);
  }, []); // Remove showToast dependency if it's unstable

  useEffect(() => {
    const checkStatus = async () => {
      // Skip check if we're already on the setup page
      if (location.pathname === '/setup') {
        setIsInitializing(false);
        return;
      }

      // Only check if we haven't checked yet (isInstalled === null)
      if (isInstalled === null) {
        try {
          await checkSetupStatus();
        } catch (error) {
          console.error('Setup status check failed:', error);
          // On error, we'll show an error screen (handled below)
        } finally {
          setIsInitializing(false);
        }
      } else {
        setIsInitializing(false);
      }
    };

    checkStatus();
  }, [isInstalled, location.pathname, checkSetupStatus]);

  // Redirect to setup if installation is not complete
  useEffect(() => {
    if (!isInitializing && isInstalled === false && location.pathname !== '/setup') {
      console.log('🔄 Installation not complete, redirecting to setup wizard...');
      navigate('/setup', { replace: true });
    }
  }, [isInitializing, isInstalled, location.pathname, navigate]);

  // Show loading screen while checking
  if (isInitializing || isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 dark:border-blue-400 mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">{t('setup.guard.checking')}</p>
        </div>
      </div>
    );
  }

  // Show error screen if check failed
  if (checkError && isInstalled === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="max-w-md w-full bg-white dark:bg-gray-800 shadow-lg rounded-lg p-8">
          <div className="text-center">
            <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100 dark:bg-red-900/30 mb-4">
              <svg
                className="h-6 w-6 text-red-600 dark:text-red-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
              {t('setup.guard.serverError')}
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
              {checkError}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              {t('setup.guard.retryButton')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // If we're on the setup page, always allow access
  if (location.pathname === '/setup') {
    return <Outlet />;
  }

  // If installation is complete, render child routes
  if (isInstalled === true) {
    return (
      <>
        <Outlet />
        <PluginModal />
      </>
    );
  }

  // Fallback: show nothing while redirecting
  return null;
};

export default RootLayout;

