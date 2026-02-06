/**
 * Debug Messages List
 * Displays the chat messages for device debugging
 */

import { useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  User,
  Bot,
  Wrench,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  Info,
  Image as ImageIcon,
} from 'lucide-react';
import { useDeviceDebugStore } from '@/stores/deviceDebugStore';
import type { DebugMessage } from '@/types/deviceDebug';

interface MessageProps {
  message: DebugMessage;
}

function UserMessage({ message }: MessageProps) {
  return (
    <div className="flex justify-end mb-8 animate-in slide-in-from-right-4 duration-500">
      <div className="flex max-w-[85%] items-start gap-4">
        <div className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl blur opacity-20 group-hover:opacity-40 transition duration-500" />
          <div className="relative rounded-2xl rounded-tr-sm bg-slate-800/80 border border-white/10 px-5 py-4 text-slate-100 shadow-2xl backdrop-blur-md">
            <p className="whitespace-pre-wrap text-sm leading-relaxed font-medium tracking-wide">{message.content}</p>
          </div>
        </div>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 border border-white/10 shadow-2xl group-hover:scale-110 transition-transform">
          <User className="h-5 w-5 text-blue-400" />
        </div>
      </div>
    </div>
  );
}

function ThinkingMessage({ message }: MessageProps) {
  return (
    <div className="flex justify-start mb-8 animate-in slide-in-from-left-4 duration-500">
      <div className="flex max-w-[85%] items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-slate-900 border border-white/5 shadow-2xl">
          <div className="relative">
            <div className="absolute inset-0 bg-blue-500/20 blur-md rounded-full animate-pulse" />
            <Loader2 className="h-5 w-5 animate-spin text-blue-400 relative z-10" />
          </div>
        </div>
        <div className="rounded-2xl rounded-tl-sm bg-white/5 border border-white/5 px-5 py-4 backdrop-blur-3xl shadow-inner">
          <div className="flex items-center gap-3 mb-2">
            <span className="text-[10px] font-black text-blue-500 uppercase tracking-[0.2em]">Neural Processing</span>
            <div className="flex gap-1.5">
              <div className="w-1 h-1 rounded-full bg-blue-500/40 animate-bounce" />
              <div className="w-1 h-1 rounded-full bg-blue-500/40 animate-bounce [animation-delay:0.2s]" />
              <div className="w-1 h-1 rounded-full bg-blue-500/40 animate-bounce [animation-delay:0.4s]" />
            </div>
          </div>
          <p className="text-sm italic text-slate-400 leading-relaxed font-medium">{message.content}</p>
          {message.iteration && message.maxIterations && (
            <div className="mt-4 flex items-center gap-3">
              <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden border border-white/5">
                <div 
                  className="h-full bg-gradient-to-r from-blue-600 to-indigo-500 transition-all duration-1000 ease-out shadow-[0_0_10px_rgba(37,99,235,0.5)]" 
                  style={{ width: `${(message.iteration / message.maxIterations) * 100}%` }}
                />
              </div>
              <span className="text-[10px] font-black font-mono text-slate-500 tracking-tighter">
                {message.iteration} / {message.maxIterations}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ToolCallMessage({ message }: MessageProps) {
  return (
    <div className="flex justify-start mb-8 animate-in fade-in zoom-in-95 duration-500">
      <div className="flex max-w-[90%] items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-indigo-500/10 border border-indigo-500/20 shadow-2xl">
          <Wrench className="h-5 w-5 text-indigo-400" />
        </div>
        <div className="rounded-[1.5rem] rounded-tl-sm border border-white/10 bg-slate-900/60 px-6 py-5 shadow-[0_20px_50px_rgba(0,0,0,0.3)] backdrop-blur-2xl relative overflow-hidden group">
          <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500/50" />
          <div className="flex items-center justify-between gap-8 mb-4">
            <div className="flex items-center gap-3">
              <div className="w-2 h-2 rounded-full bg-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.8)] animate-pulse" />
              <span className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em]">Invoking System Tool</span>
            </div>
            <span className="text-xs font-mono font-black text-white bg-indigo-500/20 px-3 py-1 rounded-lg border border-indigo-500/20 shadow-inner tracking-tight">
              {message.toolName}
            </span>
          </div>
          {message.toolArgs && Object.keys(message.toolArgs).length > 0 && (
            <div className="rounded-xl bg-black/40 border border-white/5 p-4 font-mono relative">
              <div className="flex items-center gap-2 mb-3 opacity-40">
                <Info className="w-3.5 h-3.5" />
                <span className="text-[9px] font-black uppercase tracking-[0.2em]">Payload Configuration</span>
              </div>
              <pre className="text-[11px] text-indigo-300/80 overflow-x-auto custom-scrollbar leading-relaxed">
                {JSON.stringify(message.toolArgs, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ToolResultMessage({ message }: MessageProps) {
  const { t } = useTranslation();

  return (
    <div className="flex justify-start mb-8 animate-in fade-in slide-in-from-bottom-2 duration-500">
      <div className="flex max-w-[90%] items-start gap-4">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border shadow-2xl transition-all duration-500 ${
            message.toolSuccess 
              ? 'bg-emerald-500/10 border-emerald-500/20 shadow-emerald-500/5' 
              : 'bg-rose-500/10 border-rose-500/20 shadow-rose-500/5'
          }`}
        >
          {message.toolSuccess ? (
            <CheckCircle className="h-5 w-5 text-emerald-400" />
          ) : (
            <XCircle className="h-5 w-5 text-rose-400" />
          )}
        </div>
        <div
          className={`rounded-[1.5rem] rounded-tl-sm border px-6 py-5 shadow-[0_25px_60px_rgba(0,0,0,0.4)] backdrop-blur-3xl relative overflow-hidden ${
            message.toolSuccess
              ? 'border-emerald-500/20 bg-slate-900/40'
              : 'border-rose-500/20 bg-slate-900/40'
          }`}
        >
          <div className={`absolute top-0 left-0 w-1 h-full ${message.toolSuccess ? 'bg-emerald-500/40' : 'bg-rose-500/40'}`} />
          <div className="flex items-center justify-between gap-8 mb-4">
            <div className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full ${message.toolSuccess ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)]' : 'bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.8)]'}`} />
              <span className={`text-[10px] font-black uppercase tracking-[0.2em] ${message.toolSuccess ? 'text-emerald-400' : 'text-rose-400'}`}>
                Execution Result
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono font-black text-slate-300 tracking-tight">
                {message.toolName}
              </span>
              <span
                className={`rounded-lg px-2.5 py-1 text-[9px] font-black uppercase tracking-widest border transition-all ${
                  message.toolSuccess
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                    : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                }`}
              >
                {message.toolSuccess
                  ? t('deviceDebug.success', 'Success')
                  : t('deviceDebug.failed', 'Failed')}
              </span>
            </div>
          </div>
          {message.content && (
            <div className="rounded-xl bg-black/30 p-4 border border-white/5 shadow-inner">
              <p className="text-xs text-slate-300 leading-relaxed font-mono tracking-tight">{message.content}</p>
            </div>
          )}
          {message.hasScreenshot && message.screenshotData && (
            <div className="mt-5 group/img relative">
              <div className="absolute -inset-2 bg-blue-500/10 rounded-[1.5rem] blur-xl opacity-0 group-hover/img:opacity-100 transition duration-700" />
              <div className="relative rounded-2xl border border-white/10 overflow-hidden bg-black shadow-2xl">
                <div className="absolute top-3 left-3 z-10 flex items-center gap-2 px-3 py-1.5 bg-black/60 backdrop-blur-xl rounded-xl border border-white/10 shadow-2xl">
                  <ImageIcon className="h-3.5 w-3.5 text-blue-400" />
                  <span className="text-[9px] font-black text-white uppercase tracking-[0.2em]">Visual Capture</span>
                </div>
                <img
                  src={`data:image/png;base64,${message.screenshotData}`}
                  alt="Screenshot"
                  className="max-h-80 w-full object-contain hover:scale-[1.03] transition-transform duration-700 cursor-zoom-in"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AIResponseMessage({ message }: MessageProps) {
  return (
    <div className="flex justify-start mb-8 animate-in slide-in-from-left-4 duration-500">
      <div className="flex max-w-[85%] items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-purple-500/10 border border-purple-500/20 shadow-2xl group-hover:scale-110 transition-transform">
          <Bot className="h-5 w-5 text-purple-400" />
        </div>
        <div className="relative group">
          <div className="absolute -inset-1 bg-gradient-to-r from-purple-600 to-blue-600 rounded-2xl blur opacity-10 group-hover:opacity-25 transition duration-1000" />
          <div className="relative rounded-2xl rounded-tl-sm bg-slate-800/60 border border-white/10 px-6 py-5 text-slate-100 shadow-[0_20px_50px_rgba(0,0,0,0.3)] backdrop-blur-2xl">
            <p className="whitespace-pre-wrap text-sm leading-relaxed font-medium tracking-wide">{message.content}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ErrorMessage({ message }: MessageProps) {
  return (
    <div className="flex justify-start">
      <div className="flex max-w-[80%] items-start gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100">
          <AlertCircle className="h-4 w-4 text-red-600" />
        </div>
        <div className="rounded-2xl rounded-tl-md border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-900">{message.content}</p>
          {message.errorCode && (
            <p className="mt-1 text-xs text-red-600">
              Code: {message.errorCode}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function SystemMessage({ message }: MessageProps) {
  return (
    <div className="flex justify-center">
      <div className="flex items-center gap-2 rounded-full bg-gray-100 px-4 py-2">
        <Info className="h-3 w-3 text-gray-500" />
        <span className="text-xs text-gray-600">{message.content}</span>
      </div>
    </div>
  );
}

function MessageItem({ message }: MessageProps) {
  switch (message.type) {
    case 'user':
      return <UserMessage message={message} />;
    case 'thinking':
      return <ThinkingMessage message={message} />;
    case 'tool_call':
      return <ToolCallMessage message={message} />;
    case 'tool_result':
      return <ToolResultMessage message={message} />;
    case 'ai_response':
      return <AIResponseMessage message={message} />;
    case 'error':
      return <ErrorMessage message={message} />;
    case 'system':
      return <SystemMessage message={message} />;
    default:
      return null;
  }
}

export default function DebugMessagesList() {
  const { t } = useTranslation();
  const { messages, isExecuting } = useDeviceDebugStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center">
          <Bot className="mx-auto h-12 w-12 text-gray-300" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">
            {t('deviceDebug.emptyState.title', 'Start Debugging')}
          </h3>
          <p className="mt-2 text-sm text-gray-500">
            {t(
              'deviceDebug.emptyState.description',
              'Enter a command to start controlling the device'
            )}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
      {isExecuting && messages[messages.length - 1]?.type !== 'thinking' && (
        <div className="flex justify-center">
          <div className="flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2">
            <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
            <span className="text-sm text-blue-600">
              {t('deviceDebug.processing', 'Processing...')}
            </span>
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
}
