/**
 * Device Debug Store
 * Zustand store for device debug chat state management
 */

import { create } from 'zustand';
import { v4 as uuidv4 } from 'uuid';
import type { Device } from '@/types/deviceControl';
import type {
  AgentEvent,
  DebugMessage,
  DebugStats,
  ExecutionStep,
  Screenshot,
  DeviceDebugChatRequest,
} from '@/types/deviceDebug';
import * as deviceDebugApi from '@/services/deviceDebugApi';

interface DeviceDebugState {
  // Session state
  sessionId: string | null;
  device: Device | null;
  isConnected: boolean;

  // Messages
  messages: DebugMessage[];

  // Execution state
  isExecuting: boolean;
  currentIteration: number;
  maxIterations: number;
  runId: string | null;

  // Screenshots
  screenshots: Screenshot[];
  latestScreenshot: Screenshot | null;

  // Timeline
  executionSteps: ExecutionStep[];

  // Stats
  stats: DebugStats;

  // Error
  error: string | null;

  // Abort controller for cancelling requests
  abortController: AbortController | null;

  // Actions
  setDevice: (device: Device | null) => void;
  startSession: () => void;
  endSession: () => void;
  sendMessage: (message: string, options?: {
    model?: string;
    maxIterations?: number;
    systemPrompt?: string;
  }) => Promise<void>;
  cancelExecution: () => void;
  handleAgentEvent: (event: AgentEvent) => void;
  clearMessages: () => void;
  clearError: () => void;
}

const initialStats: DebugStats = {
  toolCalls: 0,
  screenshotsCount: 0,
  totalDuration: 0,
  iterations: 0,
  errors: 0,
};

export const useDeviceDebugStore = create<DeviceDebugState>((set, get) => ({
  // Initial state
  sessionId: null,
  device: null,
  isConnected: false,
  messages: [],
  isExecuting: false,
  currentIteration: 0,
  maxIterations: 10,
  runId: null,
  screenshots: [],
  latestScreenshot: null,
  executionSteps: [],
  stats: { ...initialStats },
  error: null,
  abortController: null,

  // Set current device
  setDevice: (device) => {
    set({ device, isConnected: device?.status === 'online' });
  },

  // Start a new debug session
  startSession: () => {
    const sessionId = uuidv4();
    set({
      sessionId,
      messages: [],
      executionSteps: [],
      screenshots: [],
      latestScreenshot: null,
      stats: { ...initialStats },
      error: null,
      runId: null,
      currentIteration: 0,
    });
  },

  // End the current session
  endSession: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
    }
    set({
      sessionId: null,
      isExecuting: false,
      abortController: null,
    });
  },

  // Send a message to the device
  sendMessage: async (message, options) => {
    const { device, isExecuting } = get();

    if (!device) {
      set({ error: 'No device selected' });
      return;
    }

    if (isExecuting) {
      set({ error: 'Already executing a command' });
      return;
    }

    // Add user message
    const userMessage: DebugMessage = {
      id: uuidv4(),
      type: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    };

    const abortController = new AbortController();

    set((state) => ({
      messages: [...state.messages, userMessage],
      isExecuting: true,
      error: null,
      abortController,
      currentIteration: 0,
    }));

    const request: DeviceDebugChatRequest = {
      device_id: device.id,
      message,
      model: options?.model,
      max_iterations: options?.maxIterations,
      system_prompt: options?.systemPrompt,
    };

    const startTime = Date.now();

    try {
      await deviceDebugApi.startDeviceDebugChat(
        request,
        {
          onEvent: (event) => get().handleAgentEvent(event),
          onClose: () => {
            const duration = Date.now() - startTime;
            set((state) => ({
              isExecuting: false,
              abortController: null,
              stats: {
                ...state.stats,
                totalDuration: state.stats.totalDuration + duration,
              },
            }));
          },
          onError: (error) => {
            const errorMessage = error instanceof Error ? error.message : 'Unknown error';
            set({
              isExecuting: false,
              error: errorMessage,
              abortController: null,
            });
          },
        },
        abortController.signal
      );
    } catch (error) {
      // Error handling is done in onError callback
      if (error instanceof Error && error.name !== 'AbortError') {
        set({
          isExecuting: false,
          error: error.message,
          abortController: null,
        });
      }
    }
  },

  // Cancel ongoing execution
  cancelExecution: () => {
    const { abortController } = get();
    if (abortController) {
      abortController.abort();
      set({
        isExecuting: false,
        abortController: null,
      });

      // Add cancellation message
      const cancelMessage: DebugMessage = {
        id: uuidv4(),
        type: 'system',
        content: 'Execution cancelled by user',
        timestamp: new Date().toISOString(),
      };
      set((state) => ({
        messages: [...state.messages, cancelMessage],
      }));
    }
  },

  // Handle agent events from SSE stream
  handleAgentEvent: (event) => {
    const timestamp = event.timestamp || new Date().toISOString();

    set((state) => {
      const updates: Partial<DeviceDebugState> = {};
      const newMessages = [...state.messages];
      const newSteps = [...state.executionSteps];
      const newStats = { ...state.stats };

      switch (event.event_type) {
        case 'started':
          updates.runId = event.run_id;
          updates.maxIterations = event.max_iterations || 10;
          newMessages.push({
            id: uuidv4(),
            type: 'system',
            content: event.content || 'Starting task execution...',
            timestamp,
          });
          break;

        case 'tools_loaded':
          newMessages.push({
            id: uuidv4(),
            type: 'system',
            content: event.content || `Loaded ${event.metadata?.tool_names?.length || 0} tools`,
            timestamp,
          });
          break;

        case 'thinking':
          updates.currentIteration = event.iteration || state.currentIteration;
          newStats.iterations = event.iteration || newStats.iterations;
          newMessages.push({
            id: uuidv4(),
            type: 'thinking',
            content: event.content || 'Analyzing...',
            timestamp,
            iteration: event.iteration,
            maxIterations: event.max_iterations,
          });
          newSteps.push({
            id: uuidv4(),
            timestamp,
            type: 'thinking',
            content: event.content,
            iteration: event.iteration,
          });
          break;

        case 'tool_call':
          if (event.tool_call) {
            newStats.toolCalls++;
            newMessages.push({
              id: uuidv4(),
              type: 'tool_call',
              content: `Executing: ${event.tool_call.name}`,
              timestamp,
              toolName: event.tool_call.name,
              toolArgs: event.tool_call.arguments,
            });
            newSteps.push({
              id: uuidv4(),
              timestamp,
              type: 'tool_call',
              toolName: event.tool_call.name,
              toolArgs: event.tool_call.arguments,
              iteration: event.iteration,
            });
          }
          break;

        case 'tool_result':
          if (event.tool_result) {
            const hasImage = event.tool_result.has_image;
            const imageData = event.tool_result.image_data;

            // Add screenshot if present
            if (hasImage && imageData) {
              const screenshot: Screenshot = {
                id: uuidv4(),
                timestamp,
                data: imageData,
                toolName: event.tool_result.name,
                iteration: event.iteration,
              };
              updates.screenshots = [...state.screenshots, screenshot];
              updates.latestScreenshot = screenshot;
              newStats.screenshotsCount++;
            }

            newMessages.push({
              id: uuidv4(),
              type: 'tool_result',
              content: event.tool_result.content || (event.tool_result.success ? 'Success' : 'Failed'),
              timestamp,
              toolName: event.tool_result.name,
              toolSuccess: event.tool_result.success,
              hasScreenshot: hasImage,
              screenshotData: imageData,
            });

            newSteps.push({
              id: uuidv4(),
              timestamp,
              type: 'tool_result',
              toolName: event.tool_result.name,
              success: event.tool_result.success,
              hasScreenshot: hasImage,
              screenshotData: imageData,
              content: event.tool_result.content,
              iteration: event.iteration,
            });
          }
          break;

        case 'completed':
          newMessages.push({
            id: uuidv4(),
            type: 'ai_response',
            content: event.final_result || event.content || 'Task completed',
            timestamp,
          });
          newSteps.push({
            id: uuidv4(),
            timestamp,
            type: 'completed',
            content: event.final_result || event.content,
            iteration: event.iteration,
          });
          updates.isExecuting = false;
          break;

        case 'error':
          newStats.errors++;
          newMessages.push({
            id: uuidv4(),
            type: 'error',
            content: event.error || 'An error occurred',
            timestamp,
            errorCode: event.error_code,
          });
          newSteps.push({
            id: uuidv4(),
            timestamp,
            type: 'error',
            content: event.error,
            iteration: event.iteration,
          });
          updates.error = event.error || null;
          updates.isExecuting = false;
          break;
      }

      return {
        ...updates,
        messages: newMessages,
        executionSteps: newSteps,
        stats: newStats,
      };
    });
  },

  // Clear all messages
  clearMessages: () => {
    set({
      messages: [],
      executionSteps: [],
      screenshots: [],
      latestScreenshot: null,
      stats: { ...initialStats },
    });
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },
}));
