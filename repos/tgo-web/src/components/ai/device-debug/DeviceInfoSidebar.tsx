/**
 * Device Info Sidebar
 * Shows device information, AI agent selector, and quick commands
 */

import { useTranslation } from 'react-i18next';
import {
  Monitor,
  Smartphone,
  Camera,
  Home,
  Globe,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { useDeviceDebugStore } from '@/stores/deviceDebugStore';

interface QuickCommand {
  id: string;
  label: string;
  icon: React.ReactNode;
  command: string;
}

export default function DeviceInfoSidebar() {
  const { t } = useTranslation();
  const {
    device,
    isConnected,
    isExecuting,
    sendMessage,
    clearMessages,
    stats,
  } = useDeviceDebugStore();

  // Quick commands
  const quickCommands: QuickCommand[] = [
    {
      id: 'screenshot',
      label: t('deviceDebug.quickCommands.screenshot', '截取屏幕'),
      icon: <Camera className="h-4 w-4" />,
      command: 'Take a screenshot of the current screen',
    },
    {
      id: 'desktop',
      label: t('deviceDebug.quickCommands.desktop', '返回桌面'),
      icon: <Home className="h-4 w-4" />,
      command: 'Go to the desktop by minimizing all windows',
    },
    {
      id: 'browser',
      label: t('deviceDebug.quickCommands.browser', '打开浏览器'),
      icon: <Globe className="h-4 w-4" />,
      command: 'Open the default web browser',
    },
    {
      id: 'refresh',
      label: t('deviceDebug.quickCommands.refresh', '刷新状态'),
      icon: <RefreshCw className="h-4 w-4" />,
      command: 'Take a screenshot to see the current screen state',
    },
  ];

  const handleQuickCommand = (command: string) => {
    if (!isExecuting && isConnected) {
      sendMessage(command);
    }
  };

  if (!device) return null;

  return (
    <div className="flex flex-col h-full bg-transparent">
      <div className="flex-1 overflow-y-auto custom-scrollbar p-8 space-y-10">
        {/* Device Info Section */}
        <section>
          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-5 flex items-center gap-3 px-1">
            <div className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
            {t('deviceDebug.deviceInfo', 'Hardware Specs')}
          </h3>
          <div className="bg-white/5 rounded-[2rem] border border-white/5 p-5 space-y-5 shadow-inner relative overflow-hidden group">
            <div className="absolute -top-10 -right-10 w-24 h-24 bg-blue-500/10 blur-2xl rounded-full group-hover:bg-blue-500/20 transition-colors duration-700" />
            <div className="flex items-center gap-5 relative z-10">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 border border-white/10 shadow-2xl group-hover:scale-110 transition-transform duration-500">
                {device.device_type === 'desktop' ? (
                  <Monitor className="h-7 w-7 text-blue-400" />
                ) : (
                  <Smartphone className="h-7 w-7 text-blue-400" />
                )}
              </div>
              <div>
                <p className="font-black text-white text-lg tracking-tight leading-tight">{device.device_name}</p>
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[9px] font-black uppercase tracking-[0.15em] text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded-md border border-blue-500/20">
                    {device.device_type === 'desktop' ? 'Desktop' : 'Mobile'}
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-3 pt-4 border-t border-white/5 relative z-10">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500 font-black uppercase tracking-widest">OS Architecture</span>
                <span className="text-slate-300 font-mono font-bold">{device.os} {device.os_version}</span>
              </div>
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-slate-500 font-black uppercase tracking-widest">Display Output</span>
                <span className="text-slate-300 font-mono font-bold">{device.screen_resolution || 'Auto Detect'}</span>
              </div>
            </div>
          </div>
        </section>

        {/* Session Stats */}
        <section>
          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-5 flex items-center gap-3 px-1">
            <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(168,85,247,0.8)]" />
            {t('deviceDebug.sessionStats', 'Telemetry')}
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white/5 rounded-2xl border border-white/5 p-5 text-center group hover:bg-white/10 transition-all duration-500 shadow-sm">
              <p className="text-3xl font-black text-white group-hover:text-blue-400 transition-colors font-mono tracking-tighter">{stats.toolCalls}</p>
              <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] mt-2">
                {t('deviceDebug.toolCalls', 'Calls')}
              </p>
            </div>
            <div className="bg-white/5 rounded-2xl border border-white/5 p-5 text-center group hover:bg-white/10 transition-all duration-500 shadow-sm">
              <p className="text-3xl font-black text-white group-hover:text-purple-400 transition-colors font-mono tracking-tighter">{stats.screenshotsCount}</p>
              <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] mt-2">
                {t('deviceDebug.screenshots', 'Captures')}
              </p>
            </div>
            <div className="bg-white/5 rounded-2xl border border-white/5 p-5 text-center group hover:bg-white/10 transition-all duration-500 shadow-sm">
              <p className="text-3xl font-black text-white group-hover:text-emerald-400 transition-colors font-mono tracking-tighter">{stats.iterations}</p>
              <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] mt-2">
                {t('deviceDebug.iterations', 'Cycles')}
              </p>
            </div>
            <div className="bg-white/5 rounded-2xl border border-white/5 p-5 text-center group hover:bg-white/10 transition-all duration-500 shadow-sm">
              <p className="text-3xl font-black text-rose-500 font-mono tracking-tighter">{stats.errors}</p>
              <p className="text-[9px] font-black text-slate-500 uppercase tracking-[0.2em] mt-2">
                {t('deviceDebug.errors', 'Faults')}
              </p>
            </div>
          </div>
        </section>

        {/* Quick Commands */}
        <section>
          <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] mb-5 flex items-center gap-3 px-1">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
            {t('deviceDebug.quickCommands.title', 'Directives')}
          </h3>
          <div className="grid grid-cols-1 gap-3">
            {quickCommands.map((cmd) => (
              <button
                key={cmd.id}
                onClick={() => handleQuickCommand(cmd.command)}
                disabled={isExecuting || !isConnected}
                className="flex items-center gap-4 px-5 py-4 bg-white/5 hover:bg-white/10 disabled:opacity-20 disabled:cursor-not-allowed text-slate-300 hover:text-white rounded-2xl border border-white/5 hover:border-white/10 transition-all group relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 via-blue-500/0 to-blue-500/0 group-hover:via-blue-500/5 transition-all duration-700" />
                <div className="p-2.5 bg-slate-900 rounded-xl group-hover:scale-110 transition-transform duration-500 border border-white/5 shadow-2xl relative z-10">
                  {cmd.icon}
                </div>
                <span className="text-xs font-black uppercase tracking-widest relative z-10">{cmd.label}</span>
              </button>
            ))}
          </div>
        </section>
      </div>

      {/* Actions */}
      <div className="p-8 border-t border-white/5 bg-slate-900/40 backdrop-blur-2xl">
        <button
          onClick={clearMessages}
          disabled={isExecuting}
          className="w-full flex items-center justify-center gap-3 px-6 py-4 rounded-[1.25rem] text-[11px] font-black uppercase tracking-[0.2em] text-rose-500 hover:bg-rose-500 hover:text-white transition-all disabled:opacity-20 border border-rose-500/20 shadow-lg shadow-rose-500/5 active:scale-95"
        >
          <Trash2 className="h-4 w-4" />
          {t('deviceDebug.clearSession', 'Clear Logs')}
        </button>
      </div>
    </div>
  );
}
