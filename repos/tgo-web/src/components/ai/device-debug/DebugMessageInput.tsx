/**
 * Debug Message Input
 * Input component for sending commands to the device
 */

import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Send, Square, Loader2, AlertCircle } from 'lucide-react';
import { useDeviceDebugStore } from '@/stores/deviceDebugStore';

export default function DebugMessageInput() {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const {
    isExecuting,
    isConnected,
    sendMessage,
    cancelExecution,
    error,
    clearError,
  } = useDeviceDebugStore();

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        200
      )}px`;
    }
  }, [input]);

  // Clear error when input changes
  useEffect(() => {
    if (error && input) {
      clearError();
    }
  }, [input, error, clearError]);

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();

    const trimmedInput = input.trim();
    if (!trimmedInput || isExecuting || !isConnected) return;

    setInput('');
    await sendMessage(trimmedInput);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleCancel = () => {
    cancelExecution();
  };

  return (
    <div className="space-y-4">
      {/* Error message */}
      {error && (
        <div className="mx-6 flex items-center gap-3 rounded-2xl bg-rose-500/10 border border-rose-500/20 px-5 py-3 text-sm text-rose-400 animate-in slide-in-from-bottom-2 duration-300">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="font-bold tracking-tight">{error}</span>
        </div>
      )}

      {/* Input form */}
      <form onSubmit={handleSubmit} className="flex items-end gap-4 p-6 bg-slate-900/40 backdrop-blur-3xl border-t border-white/5">
        <div className="relative flex-1 group">
          <div className="absolute -inset-1 bg-gradient-to-r from-blue-600/20 to-purple-600/20 rounded-[1.5rem] blur-md opacity-0 group-focus-within:opacity-100 transition duration-700" />
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isConnected
                ? t(
                    'deviceDebug.inputPlaceholder',
                    'Describe the task for AI Agent... (e.g., "Open Chrome and search for latest AI news")'
                  )
                : t(
                    'deviceDebug.deviceDisconnected',
                    'System Offline - Connection Lost'
                  )
            }
            disabled={isExecuting || !isConnected}
            className="relative w-full resize-none rounded-[1.25rem] border border-white/10 bg-black/40 px-6 py-4 pr-16 text-slate-100 placeholder-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-4 focus:ring-blue-500/5 transition-all disabled:cursor-not-allowed disabled:opacity-30 text-sm leading-relaxed font-medium shadow-inner"
            rows={1}
          />
          <div className="absolute right-5 bottom-4 flex items-center gap-2 pointer-events-none">
            <span className="text-[9px] font-black text-slate-700 uppercase tracking-widest hidden sm:block bg-white/5 px-2 py-1 rounded-md border border-white/5">Enter</span>
          </div>
        </div>

        {isExecuting ? (
          <button
            type="button"
            onClick={handleCancel}
            className="flex h-[56px] w-[56px] shrink-0 items-center justify-center rounded-[1.25rem] bg-rose-500/10 border border-rose-500/20 text-rose-500 hover:bg-rose-500 hover:text-white transition-all active:scale-90 shadow-2xl shadow-rose-500/10 group relative overflow-hidden"
            title={t('common.cancel', 'Abort Execution')}
          >
            <div className="absolute inset-0 bg-rose-500/20 animate-pulse" />
            <Square className="h-5 w-5 fill-current group-hover:scale-90 transition-transform relative z-10" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() || !isConnected}
            className="flex h-[56px] w-[56px] shrink-0 items-center justify-center rounded-[1.25rem] bg-blue-600 text-white hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-700 disabled:border-white/5 border border-white/10 transition-all active:scale-90 shadow-[0_15px_30px_rgba(37,99,235,0.3)] disabled:shadow-none group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-tr from-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            {isExecuting ? (
              <Loader2 className="h-5 w-5 animate-spin relative z-10" />
            ) : (
              <Send className="h-5 w-5 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform relative z-10" />
            )}
          </button>
        )}
      </form>

      {/* Helper text */}
      <div className="flex items-center justify-center gap-6 pb-4">
        <div className="flex items-center gap-2">
          <div className="w-1 h-1 rounded-full bg-blue-500/40" />
          <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.25em]">
            {t('deviceDebug.inputHelp', 'Shift + Enter for multiline')}
          </p>
        </div>
        <div className="w-1 h-1 rounded-full bg-slate-800" />
        <div className="flex items-center gap-2">
          <div className="w-1 h-1 rounded-full bg-purple-500/40" />
          <p className="text-[9px] font-black text-slate-600 uppercase tracking-[0.25em]">
            AI Protocol v2.4.0
          </p>
        </div>
      </div>
    </div>
  );
}
