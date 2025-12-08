import { create } from 'zustand';
import { setupApiService, type SetupStatusResponse } from '@/services/setupApi';

interface SetupState {
  // State
  isInstalled: boolean | null; // null = not checked yet, true/false = checked
  hasAdmin: boolean;
  hasUserStaff: boolean;
  hasLLMConfig: boolean;
  setupCompletedAt: string | null;
  isChecking: boolean;
  checkError: string | null;

  // Actions
  checkSetupStatus: () => Promise<void>;
  resetSetupState: () => void;
}

/**
 * Setup Store
 * Manages system installation status
 */
export const useSetupStore = create<SetupState>((set) => ({
  // Initial state
  isInstalled: null, // null means we haven't checked yet
  hasAdmin: false,
  hasUserStaff: false,
  hasLLMConfig: false,
  setupCompletedAt: null,
  isChecking: false,
  checkError: null,

  /**
   * Check setup status from API
   */
  checkSetupStatus: async () => {
    set({ isChecking: true, checkError: null });

    try {
      const response: SetupStatusResponse = await setupApiService.getStatus();

      set({
        isInstalled: response.is_installed,
        hasAdmin: response.has_admin,
        hasUserStaff: response.has_user_staff,
        hasLLMConfig: response.has_llm_config,
        setupCompletedAt: response.setup_completed_at,
        isChecking: false,
        checkError: null,
      });

      console.log('✅ Setup status checked:', {
        isInstalled: response.is_installed,
        hasAdmin: response.has_admin,
        hasUserStaff: response.has_user_staff,
        hasLLMConfig: response.has_llm_config,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to check setup status';
      
      set({
        isChecking: false,
        checkError: errorMessage,
      });

      console.error('❌ Failed to check setup status:', error);
      
      // Re-throw the error so the caller can handle it
      throw error;
    }
  },

  /**
   * Reset setup state (useful for testing or after setup completion)
   */
  resetSetupState: () => {
    set({
      isInstalled: null,
      hasAdmin: false,
      hasUserStaff: false,
      hasLLMConfig: false,
      setupCompletedAt: null,
      isChecking: false,
      checkError: null,
    });
  },
}));

