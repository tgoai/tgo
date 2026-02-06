/**
 * Device Debug Chat Page
 * Main page for debugging devices through natural language chat
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ArrowLeft, Loader2, AlertCircle, Terminal } from 'lucide-react';
import Button from '@/components/ui/Button';
import { useDeviceDebugStore } from '@/stores/deviceDebugStore';
import { useDeviceControlStore } from '@/stores/deviceControlStore';
import DeviceInfoSidebar from './DeviceInfoSidebar';
import DebugMessagesList from './DebugMessagesList';
import DebugMessageInput from './DebugMessageInput';
import ScreenshotPanel from './ScreenshotPanel';
import ExecutionTimeline from './ExecutionTimeline';

export default function DeviceDebugChat() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const {
    device,
    setDevice,
    startSession,
    endSession,
    isExecuting,
  } = useDeviceDebugStore();

  const { devices, loadDevices } = useDeviceControlStore();

  // Load device data
  useEffect(() => {
    async function loadDevice() {
      setIsLoading(true);
      setLoadError(null);

      try {
        // Load devices if not loaded
        if (devices.length === 0) {
          await loadDevices();
        }

        // Find the device
        const foundDevice = devices.find((d) => d.id === deviceId);
        if (!foundDevice) {
          // Try loading again
          await loadDevices();
          const refreshedDevices = useDeviceControlStore.getState().devices;
          const device = refreshedDevices.find((d) => d.id === deviceId);
          if (!device) {
            setLoadError(t('deviceDebug.deviceNotFound', 'Device not found'));
            return;
          }
          setDevice(device);
        } else {
          setDevice(foundDevice);
        }

        // Start a new session
        startSession();
      } catch (error) {
        setLoadError(
          error instanceof Error ? error.message : t('deviceDebug.loadError', 'Failed to load device')
        );
      } finally {
        setIsLoading(false);
      }
    }

    if (deviceId) {
      loadDevice();
    }

    return () => {
      endSession();
    };
  }, [deviceId, devices, loadDevices, setDevice, startSession, endSession, t]);

  // Handle back navigation
  const handleBack = () => {
    if (isExecuting) {
      // TODO: Show confirmation dialog
    }
    navigate('/ai/device-control');
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#020617]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
          <p className="text-slate-400">{t('common.loading', 'Loading...')}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (loadError || !device) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#020617]">
        <div className="flex flex-col items-center gap-4 text-center">
          <AlertCircle className="h-12 w-12 text-red-500" />
          <h2 className="text-lg font-semibold text-slate-100">
            {t('deviceDebug.error', 'Error')}
          </h2>
          <p className="text-slate-400">{loadError || t('deviceDebug.deviceNotFound', 'Device not found')}</p>
          <Button onClick={handleBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('common.back', 'Back')}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col bg-[#020617] text-slate-300 font-sans selection:bg-blue-500/30 overflow-hidden">
      {/* Header - Advanced Glassmorphism */}
      <header className="flex items-center justify-between border-b border-white/5 bg-slate-900/40 backdrop-blur-2xl px-8 py-4 z-30 shadow-2xl">
        <div className="flex items-center gap-8">
          <button 
            onClick={handleBack}
            className="group p-2.5 hover:bg-white/5 text-slate-400 hover:text-white rounded-2xl transition-all active:scale-95 border border-white/5 hover:border-white/10 shadow-inner"
          >
            <ArrowLeft className="h-5 w-5 group-hover:-translate-x-0.5 transition-transform" />
          </button>
          <div className="flex items-center gap-5">
            <div className="relative">
              <div className="absolute -inset-1 bg-gradient-to-tr from-blue-600 to-purple-600 rounded-2xl blur-md opacity-40 animate-pulse" />
              <div className="relative p-3 bg-slate-900 rounded-2xl border border-white/10 shadow-2xl">
                <Terminal className="h-6 w-6 text-blue-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-black text-white tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                  {t('deviceDebug.title', 'Debug Console')}
                </h1>
                <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-[0.15em] ${
                  device.status === 'online' 
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]' 
                    : 'bg-slate-800 text-slate-500 border border-slate-700'
                }`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${device.status === 'online' ? 'bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.8)]' : 'bg-slate-500'}`} />
                  {device.status === 'online' ? 'System Live' : 'Offline'}
                </div>
              </div>
              <p className="text-[11px] text-slate-500 font-bold mt-1 flex items-center gap-2">
                <span className="text-blue-500/80">{device.device_name}</span>
                <span className="w-1 h-1 rounded-full bg-slate-800" />
                <span>{device.os}</span>
                <span className="w-1 h-1 rounded-full bg-slate-800" />
                <span className="text-slate-600">{device.screen_resolution || 'Auto Res'}</span>
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="hidden xl:flex items-center gap-4 px-5 py-2 bg-white/5 rounded-2xl border border-white/5 shadow-inner">
            <div className="flex flex-col items-end">
              <span className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">{t('deviceDebug.sessionTime', 'Uptime')}</span>
              <span className="text-sm font-mono text-blue-400 font-black tracking-tighter">00:12:45</span>
            </div>
            <div className="w-px h-6 bg-white/10" />
            <div className="flex flex-col items-end">
              <span className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em]">Latency</span>
              <span className="text-sm font-mono text-emerald-400 font-black tracking-tighter">24ms</span>
            </div>
          </div>
          <button 
            onClick={handleBack}
            className="rounded-2xl font-black text-[11px] uppercase tracking-widest px-6 py-3 bg-rose-500/10 hover:bg-rose-500 text-rose-500 hover:text-white border border-rose-500/20 transition-all shadow-lg shadow-rose-500/5 active:scale-95"
          >
            {t('deviceDebug.endSession', 'Terminate')}
          </button>
        </div>
      </header>

      {/* Main Content - Ultra Modern Layout */}
      <div className="flex flex-1 overflow-hidden relative">
        {/* Left Sidebar - Specs & Stats */}
        <aside className="w-80 shrink-0 overflow-y-auto border-r border-white/5 bg-slate-900/20 backdrop-blur-sm hidden lg:block custom-scrollbar z-20">
          <DeviceInfoSidebar />
        </aside>

        {/* Center - Chat Area (The "Core") */}
        <main className="flex flex-1 flex-col overflow-hidden bg-[#020617] relative z-10">
          {/* Ambient Background Glows */}
          <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-blue-600/5 blur-[120px] rounded-full pointer-events-none" />
          <div className="absolute bottom-0 right-1/4 w-[500px] h-[500px] bg-purple-600/5 blur-[120px] rounded-full pointer-events-none" />
          
          <div className="flex-1 overflow-y-auto custom-scrollbar relative z-10 px-6 py-8">
            <div className="max-w-4xl mx-auto">
              <DebugMessagesList />
            </div>
          </div>
          
          {/* Input Area - Floating Glass Dock */}
          <div className="px-8 pb-8 pt-2 relative z-20">
            <div className="max-w-4xl mx-auto relative group">
              <div className="absolute -inset-1 bg-gradient-to-r from-blue-600/20 via-purple-600/20 to-blue-600/20 rounded-[2.5rem] blur-xl opacity-0 group-focus-within:opacity-100 transition duration-1000" />
              <div className="relative bg-slate-900/80 backdrop-blur-3xl border border-white/10 rounded-[2rem] shadow-[0_20px_50px_rgba(0,0,0,0.5)] overflow-hidden">
                <DebugMessageInput />
              </div>
            </div>
          </div>
        </main>

        {/* Right Panel - Visual & Pipeline */}
        <aside className="w-[480px] shrink-0 overflow-y-auto border-l border-white/5 bg-slate-900/40 backdrop-blur-xl custom-scrollbar z-20">
          <div className="p-8 space-y-10">
            <section className="relative group">
              <div className="absolute -inset-4 bg-blue-500/5 rounded-[2.5rem] blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-700" />
              <div className="relative">
                <div className="flex items-center justify-between mb-5 px-1">
                  <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                    {t('deviceDebug.visualFeedback', 'Live Stream')}
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] font-black text-blue-400/80 bg-blue-500/10 px-2.5 py-1 rounded-lg border border-blue-500/20 uppercase tracking-tighter">
                      4K Sync
                    </span>
                  </div>
                </div>
                <div className="rounded-[2rem] overflow-hidden border border-white/10 shadow-[0_30px_60px_rgba(0,0,0,0.4)] bg-black aspect-video relative group/screen">
                  <ScreenshotPanel />
                  <div className="absolute inset-0 bg-gradient-to-tr from-blue-500/5 to-purple-500/5 opacity-0 group-hover/screen:opacity-100 transition-opacity pointer-events-none" />
                </div>
              </div>
            </section>

            <section className="relative">
              <div className="flex items-center justify-between mb-5 px-1">
                <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] flex items-center gap-3">
                  <div className="w-1.5 h-1.5 rounded-full bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.8)]" />
                  {t('deviceDebug.executionTimeline', 'Pipeline')}
                </h3>
                <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Real-time</span>
              </div>
              <div className="bg-white/5 rounded-[2rem] border border-white/5 p-2 shadow-inner">
                <ExecutionTimeline />
              </div>
            </section>
          </div>
        </aside>
      </div>
    </div>
  );
}
