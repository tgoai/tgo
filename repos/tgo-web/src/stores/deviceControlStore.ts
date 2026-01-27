/**
 * Device Control Store
 * Zustand store for device control state management
 *
 * Note: project_id is automatically obtained from JWT token by the backend,
 * so it doesn't need to be passed explicitly in API calls.
 */

import { create } from 'zustand';
import type { Device, DeviceStatus, DeviceType } from '@/types/deviceControl';
import * as deviceControlApi from '@/services/deviceControlApi';

interface DeviceControlState {
  // Data
  devices: Device[];
  selectedDevice: Device | null;
  bindCode: string | null;
  bindCodeExpiresAt: string | null;

  // UI State
  isLoading: boolean;
  isGeneratingCode: boolean;
  error: string | null;

  // Actions
  loadDevices: (deviceType?: DeviceType, status?: DeviceStatus) => Promise<void>;
  generateBindCode: () => Promise<string>;
  updateDevice: (deviceId: string, name: string) => Promise<void>;
  deleteDevice: (deviceId: string) => Promise<void>;
  disconnectDevice: (deviceId: string) => Promise<void>;
  selectDevice: (device: Device | null) => void;
  clearError: () => void;
  clearBindCode: () => void;
}

export const useDeviceControlStore = create<DeviceControlState>((set) => ({
  // Initial state
  devices: [],
  selectedDevice: null,
  bindCode: null,
  bindCodeExpiresAt: null,
  isLoading: false,
  isGeneratingCode: false,
  error: null,

  // Load devices
  loadDevices: async (deviceType, status) => {
    set({ isLoading: true, error: null });

    try {
      const response = await deviceControlApi.listDevices({
        device_type: deviceType,
        status: status,
      });
      set({ devices: response.devices, isLoading: false });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load devices';
      set({ error: message, isLoading: false });
    }
  },

  // Generate bind code
  generateBindCode: async () => {
    set({ isGeneratingCode: true, error: null });

    try {
      const response = await deviceControlApi.generateBindCode();
      set({
        bindCode: response.bind_code,
        bindCodeExpiresAt: response.expires_at,
        isGeneratingCode: false,
      });
      return response.bind_code;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to generate bind code';
      set({ error: message, isGeneratingCode: false });
      throw error;
    }
  },

  // Update device
  updateDevice: async (deviceId, name) => {
    try {
      const updated = await deviceControlApi.updateDevice(deviceId, {
        device_name: name,
      });

      // Update local state
      set((state) => ({
        devices: state.devices.map((d) => (d.id === deviceId ? updated : d)),
        selectedDevice: state.selectedDevice?.id === deviceId ? updated : state.selectedDevice,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update device';
      set({ error: message });
      throw error;
    }
  },

  // Delete device
  deleteDevice: async (deviceId) => {
    try {
      await deviceControlApi.deleteDevice(deviceId);

      // Update local state
      set((state) => ({
        devices: state.devices.filter((d) => d.id !== deviceId),
        selectedDevice: state.selectedDevice?.id === deviceId ? null : state.selectedDevice,
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to delete device';
      set({ error: message });
      throw error;
    }
  },

  // Disconnect device
  disconnectDevice: async (deviceId) => {
    try {
      await deviceControlApi.disconnectDevice(deviceId);

      // Update local state - set status to offline
      set((state) => ({
        devices: state.devices.map((d) =>
          d.id === deviceId ? { ...d, status: 'offline' as const } : d
        ),
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to disconnect device';
      set({ error: message });
      throw error;
    }
  },

  // Select device
  selectDevice: (device) => {
    set({ selectedDevice: device });
  },

  // Clear error
  clearError: () => {
    set({ error: null });
  },

  // Clear bind code
  clearBindCode: () => {
    set({ bindCode: null, bindCodeExpiresAt: null });
  },
}));
