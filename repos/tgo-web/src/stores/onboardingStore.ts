import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

/**
 * Onboarding task types
 */
export type OnboardingTask = 
  | 'platformCreated'
  | 'knowledgeBaseUploaded'
  | 'agentCreated'
  | 'messageReceived';

/**
 * Onboarding state interface
 */
interface OnboardingState {
  // Whether the user has dismissed the onboarding checklist
  isDismissed: boolean;
  
  // Task completion status
  tasksCompleted: {
    platformCreated: boolean;
    knowledgeBaseUploaded: boolean;
    agentCreated: boolean;
    messageReceived: boolean;
  };
  
  // Whether the checklist is collapsed
  isCollapsed: boolean;
  
  // Actions
  markTaskCompleted: (task: OnboardingTask) => void;
  dismissOnboarding: () => void;
  toggleCollapse: () => void;
  resetOnboarding: () => void;
  
  // Computed properties
  getCompletedCount: () => number;
  getTotalCount: () => number;
  isAllCompleted: () => boolean;
}

/**
 * Onboarding Store
 * Manages the state of the onboarding checklist
 */
export const useOnboardingStore = create<OnboardingState>()(
  devtools(
    persist(
      (set, get) => ({
        // Initial state
        isDismissed: false,
        tasksCompleted: {
          platformCreated: false,
          knowledgeBaseUploaded: false,
          agentCreated: false,
          messageReceived: false,
        },
        isCollapsed: false,
        
        // Mark a task as completed
        markTaskCompleted: (task: OnboardingTask) => {
          set(
            (state) => ({
              tasksCompleted: {
                ...state.tasksCompleted,
                [task]: true,
              },
            }),
            false,
            `markTaskCompleted:${task}`
          );
        },
        
        // Dismiss the onboarding checklist permanently
        dismissOnboarding: () => {
          set({ isDismissed: true }, false, 'dismissOnboarding');
        },
        
        // Toggle collapse state
        toggleCollapse: () => {
          set((state) => ({ isCollapsed: !state.isCollapsed }), false, 'toggleCollapse');
        },
        
        // Reset onboarding state (for testing/debugging)
        resetOnboarding: () => {
          set(
            {
              isDismissed: false,
              tasksCompleted: {
                platformCreated: false,
                knowledgeBaseUploaded: false,
                agentCreated: false,
                messageReceived: false,
              },
              isCollapsed: false,
            },
            false,
            'resetOnboarding'
          );
        },
        
        // Get the number of completed tasks
        getCompletedCount: () => {
          const { tasksCompleted } = get();
          return Object.values(tasksCompleted).filter(Boolean).length;
        },
        
        // Get the total number of tasks
        getTotalCount: () => {
          return 4;
        },
        
        // Check if all tasks are completed
        isAllCompleted: () => {
          const { tasksCompleted } = get();
          return Object.values(tasksCompleted).every(Boolean);
        },
      }),
      {
        name: 'onboarding-store',
        partialize: (state) => ({
          isDismissed: state.isDismissed,
          tasksCompleted: state.tasksCompleted,
          isCollapsed: state.isCollapsed,
        }),
      }
    ),
    { name: 'onboarding-store' }
  )
);

