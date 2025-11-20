/**
 * Store Initialization Hook
 * Handles loading mock data in development and real data in production
 */

import { useEffect } from 'react';
import { useChatStore } from '@/stores/chatStore';

import mockDataHelper from '@/utils/mockDataHelper';

/**
 * Hook to initialize all stores with appropriate data
 * Call this in your main App component or root layout
 */
export const useStoreInitialization = () => {
  // Get initialization methods from stores
  const initializeChatStore = useChatStore(state => state.initializeStore);


  useEffect(() => {
    const initializeStores = async () => {
      try {
        // Initialize all stores concurrently
        await initializeChatStore();

        if (mockDataHelper.isDevelopment()) {
          console.log('✅ Stores initialized with mock data for development');
        } else {
          console.log('✅ Stores initialized for production');
        }
      } catch (error) {
        console.error('❌ Failed to initialize stores:', error);
      }
    };

    initializeStores();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps - only run once on mount (store functions are stable)
};

export default useStoreInitialization;