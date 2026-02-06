import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import AIMenu from '../components/layout/AIMenu';

/**
 * AI Interface main page component with nested routing
 */
const AIInterface: React.FC = () => {
  const location = useLocation();
  
  // Check if we are in the workflow editor
  const isWorkflowEditor = location.pathname.includes('/workflows/') && 
    (location.pathname.endsWith('/edit') || location.pathname.endsWith('/new'));

  // Check if we are in the device debug page (full-screen mode)
  const isDeviceDebug = location.pathname.includes('/device-debug/');

  // Hide the AI menu in full-screen views
  const hideMenu = isWorkflowEditor || isDeviceDebug;

  return (
    <div className="flex h-full w-full bg-gray-50 dark:bg-gray-900">
      {/* AI Feature Menu - Hidden in workflow editor and device debug */}
      {!hideMenu && <AIMenu />}

      {/* Main Content Area - renders child routes */}
      <Outlet />
    </div>
  );
};

export default AIInterface;
