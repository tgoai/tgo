/**
 * Execution Timeline
 * Shows the timeline of executed operations
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Wrench,
  CheckCircle,
  XCircle,
  Brain,
  AlertCircle,
  ChevronDown,
  Clock,
} from 'lucide-react';
import { useDeviceDebugStore } from '@/stores/deviceDebugStore';
import type { ExecutionStep } from '@/types/deviceDebug';

interface TimelineItemProps {
  step: ExecutionStep;
  isLast: boolean;
}

function TimelineItem({ step, isLast }: TimelineItemProps) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);

  const getIcon = () => {
    switch (step.type) {
      case 'tool_call':
        return <Wrench className="h-3.5 w-3.5 text-indigo-400" />;
      case 'tool_result':
        return step.success ? (
          <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
        ) : (
          <XCircle className="h-3.5 w-3.5 text-rose-400" />
        );
      case 'thinking':
        return <Brain className="h-3.5 w-3.5 text-purple-400" />;
      case 'completed':
        return <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />;
      case 'error':
        return <AlertCircle className="h-3.5 w-3.5 text-rose-400" />;
      default:
        return <Clock className="h-3.5 w-3.5 text-slate-400" />;
    }
  };

  const getStatusColor = () => {
    switch (step.type) {
      case 'tool_call':
        return 'bg-indigo-500/10 border-indigo-500/20';
      case 'tool_result':
        return step.success ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-rose-500/10 border-rose-500/20';
      case 'thinking':
        return 'bg-purple-500/10 border-purple-500/20';
      case 'completed':
        return 'bg-emerald-500/10 border-emerald-500/20';
      case 'error':
        return 'bg-rose-500/10 border-rose-500/20';
      default:
        return 'bg-white/5 border-white/5';
    }
  };

  const getTitle = () => {
    switch (step.type) {
      case 'tool_call':
        return step.toolName || t('deviceDebug.toolCall', 'Directives');
      case 'tool_result':
        return `${step.toolName} ${
          step.success
            ? t('deviceDebug.success', 'Success')
            : t('deviceDebug.failed', 'Failed')
        }`;
      case 'thinking':
        return t('deviceDebug.thinking', 'Processing');
      case 'completed':
        return t('deviceDebug.completed', 'Task Finalized');
      case 'error':
        return t('deviceDebug.errorOccurred', 'System Fault');
      default:
        return step.type;
    }
  };

  const hasDetails =
    (step.toolArgs && Object.keys(step.toolArgs).length > 0) ||
    step.content ||
    step.hasScreenshot;

  return (
    <div className="flex gap-5 group animate-in fade-in slide-in-from-left-2 duration-500">
      {/* Timeline line and dot */}
      <div className="flex flex-col items-center">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border transition-all duration-500 group-hover:scale-110 shadow-2xl ${getStatusColor()}`}>
          {getIcon()}
        </div>
        {!isLast && <div className="w-px flex-1 bg-gradient-to-b from-white/10 to-transparent my-2" />}
      </div>

      {/* Content */}
      <div className="flex-1 pb-8">
        <div
          className={`rounded-[1.5rem] border border-white/5 bg-white/5 p-5 transition-all duration-500 hover:bg-white/10 hover:border-white/10 shadow-sm ${
            hasDetails ? 'cursor-pointer' : ''
          }`}
          onClick={() => hasDetails && setIsExpanded(!isExpanded)}
        >
          <div className="flex items-center justify-between">
            <div className="space-y-1.5">
              <p className="text-sm font-black text-slate-200 tracking-tight leading-none uppercase tracking-widest">{getTitle()}</p>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono font-black text-slate-500">
                  {new Date(step.timestamp).toLocaleTimeString()}
                </span>
                {step.iteration && (
                  <>
                    <div className="w-1 h-1 rounded-full bg-slate-800" />
                    <span className="text-[9px] font-black text-blue-500/80 uppercase tracking-widest bg-blue-500/5 px-2 py-0.5 rounded border border-blue-500/10">
                      Cycle {step.iteration}
                    </span>
                  </>
                )}
              </div>
            </div>
            {hasDetails && (
              <div className={`p-2 rounded-xl bg-slate-900 border border-white/5 transition-all duration-500 ${isExpanded ? 'rotate-180 bg-blue-600 border-blue-500 text-white' : 'text-slate-500'}`}>
                <ChevronDown className="h-4 w-4" />
              </div>
            )}
          </div>

          {/* Expanded details */}
          {isExpanded && hasDetails && (
            <div className="mt-5 space-y-5 border-t border-white/5 pt-5 animate-in slide-in-from-top-2 duration-500">
              {step.toolArgs && Object.keys(step.toolArgs).length > 0 && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 opacity-40">
                    <Wrench className="w-3.5 h-3.5" />
                    <span className="text-[9px] font-black uppercase tracking-[0.2em]">Input Parameters</span>
                  </div>
                  <pre className="overflow-x-auto rounded-xl bg-black/40 p-4 text-[11px] font-mono text-indigo-300/70 border border-white/5 custom-scrollbar leading-relaxed">
                    {JSON.stringify(step.toolArgs, null, 2)}
                  </pre>
                </div>
              )}
              {step.content && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 opacity-40">
                    <CheckCircle className="w-3.5 h-3.5" />
                    <span className="text-[9px] font-black uppercase tracking-[0.2em]">Execution Output</span>
                  </div>
                  <div className="rounded-xl bg-black/20 p-4 border border-white/5 shadow-inner">
                    <p className="text-xs text-slate-400 leading-relaxed font-mono tracking-tight">{step.content}</p>
                  </div>
                </div>
              )}
              {step.hasScreenshot && step.screenshotData && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 opacity-40">
                    <Clock className="w-3.5 h-3.5" />
                    <span className="text-[9px] font-black uppercase tracking-[0.2em]">Visual Snapshot</span>
                  </div>
                  <div className="relative group/stepimg rounded-2xl border border-white/10 overflow-hidden bg-black shadow-2xl">
                    <img
                      src={`data:image/png;base64,${step.screenshotData}`}
                      alt="Step screenshot"
                      className="max-h-64 w-full object-contain transition-transform duration-700 group-hover/stepimg:scale-105"
                    />
                    <div className="absolute inset-0 bg-blue-500/10 opacity-0 group-hover/stepimg:opacity-100 transition-opacity pointer-events-none" />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ExecutionTimeline() {
  const { t } = useTranslation();
  const { executionSteps } = useDeviceDebugStore();

  return (
    <div className="space-y-6">
      {executionSteps.length === 0 ? (
        <div className="rounded-[2.5rem] border-2 border-dashed border-white/5 bg-white/5 p-12 text-center group hover:border-white/10 transition-all duration-700">
          <div className="inline-flex p-5 bg-slate-900 rounded-[1.5rem] mb-5 group-hover:scale-110 transition-transform duration-500 border border-white/5 shadow-2xl">
            <Clock className="h-10 w-10 text-slate-700" />
          </div>
          <p className="text-[10px] font-black text-slate-600 uppercase tracking-[0.3em]">
            {t('deviceDebug.noSteps', 'Pipeline Idle - No Data')}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {executionSteps.map((step, index) => (
            <TimelineItem
              key={step.id}
              step={step}
              isLast={index === executionSteps.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
