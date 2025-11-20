import React, { useEffect, useRef } from 'react';
import { Outlet } from 'react-router-dom';
import PlatformList from '../components/platforms/PlatformList';
import { usePlatformStore } from '@/stores/platformStore';

/**
 * Platform Management layout component with nested routing
 */
const PlatformManagement: React.FC = () => {
  const initializePlatformStore = usePlatformStore(state => state.initializeStore);
  const isLoading = usePlatformStore(state => state.isLoading);
  const loadError = usePlatformStore(state => state.loadError);
  const platforms = usePlatformStore(state => state.platforms);

  // Track whether we've already attempted to initialize to prevent infinite loops
  const hasAttemptedInit = useRef(false);

  useEffect(() => {
    // Only initialize if:
    // 1. Not currently loading
    // 2. No load error (to prevent retry loop on error)
    // 3. No platforms loaded yet
    // 4. Haven't already attempted initialization
    if (!isLoading && !loadError && platforms.length === 0 && !hasAttemptedInit.current) {
      hasAttemptedInit.current = true;
      initializePlatformStore();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLoading, loadError, platforms.length]); // Don't include initializePlatformStore (it's a stable store function)

  return (
    <div className="flex h-full w-full">
      {/* Platform List Sidebar */}
      <PlatformList />

      {/* Platform Configuration Area - renders child routes */}
      <Outlet />
    </div>
  );
};

export default PlatformManagement;

