/**
 * Computer Use Session Monitor Component
 * Displays real-time status and execution history of Computer Use sessions
 */

import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Monitor,
  MousePointer,
  Keyboard,
  Scroll,
  Image,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  AlertCircle,
} from 'lucide-react';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

/**
 * Session status
 */
type SessionStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'paused'
  | 'cancelled'
  | 'max_rounds_exceeded';

/**
 * Action type
 */
type ActionType =
  | 'click'
  | 'double_click'
  | 'type'
  | 'hotkey'
  | 'key_press'
  | 'scroll'
  | 'mouse_move'
  | 'drag'
  | 'wait'
  | 'done';

/**
 * Step status
 */
type StepStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped';

/**
 * Execution step information
 */
interface ExecutionStep {
  step_id: string;
  round_number: number;
  timestamp: string;
  action_type?: ActionType;
  target_element?: string;
  reasoning?: string;
  result?: string;
  status: StepStatus;
  duration_ms?: number;
  screenshot_available?: boolean;
}

/**
 * Session information
 */
interface AgentSession {
  session_id: string;
  device_id: string;
  device_name?: string;
  task: string;
  status: SessionStatus;
  current_round: number;
  max_rounds: number;
  steps: ExecutionStep[];
  final_result?: string;
  error_message?: string;
  started_at?: string;
  completed_at?: string;
  screenshots_count: number;
  actions_count: number;
  errors_count: number;
}

interface ComputerUseSessionMonitorProps {
  sessionId: string;
  onClose: () => void;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const getActionIcon = (actionType?: ActionType) => {
  switch (actionType) {
    case 'click':
    case 'double_click':
      return <MousePointer className="w-4 h-4" />;
    case 'type':
    case 'hotkey':
    case 'key_press':
      return <Keyboard className="w-4 h-4" />;
    case 'scroll':
      return <Scroll className="w-4 h-4" />;
    default:
      return <Monitor className="w-4 h-4" />;
  }
};

const getStatusIcon = (status: StepStatus) => {
  switch (status) {
    case 'success':
      return <CheckCircle className="w-4 h-4 text-green-600" />;
    case 'failed':
      return <XCircle className="w-4 h-4 text-red-600" />;
    case 'running':
      return <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />;
    case 'skipped':
      return <Clock className="w-4 h-4 text-gray-400" />;
    default:
      return <Clock className="w-4 h-4 text-gray-400" />;
  }
};

const getSessionStatusBadge = (status: SessionStatus, t: (key: string, fallback: string) => string) => {
  const variants: Record<SessionStatus, { className: string; label: string }> = {
    pending: { className: 'bg-gray-100 text-gray-600', label: t('session.pending', 'Pending') },
    running: { className: 'bg-blue-100 text-blue-600', label: t('session.running', 'Running') },
    completed: { className: 'bg-green-100 text-green-600', label: t('session.completed', 'Completed') },
    failed: { className: 'bg-red-100 text-red-600', label: t('session.failed', 'Failed') },
    paused: { className: 'bg-amber-100 text-amber-600', label: t('session.paused', 'Paused') },
    cancelled: { className: 'bg-gray-100 text-gray-600', label: t('session.cancelled', 'Cancelled') },
    max_rounds_exceeded: { className: 'bg-red-100 text-red-600', label: t('session.maxRounds', 'Max Rounds') },
  };

  const { className, label } = variants[status] || variants.pending;

  return (
    <Badge className={`${className} border-none text-xs`}>
      {status === 'running' && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
      {status === 'completed' && <CheckCircle className="w-3 h-3 mr-1" />}
      {status === 'failed' && <XCircle className="w-3 h-3 mr-1" />}
      {label}
    </Badge>
  );
};

export function ComputerUseSessionMonitor({
  sessionId,
  onClose,
  autoRefresh = true,
  refreshInterval = 2000,
}: ComputerUseSessionMonitorProps) {
  const { t } = useTranslation();
  const [session] = useState<AgentSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const scrollRef = useRef<HTMLDivElement>(null);

  // Fetch session data
  const fetchSession = async () => {
    try {
      // TODO: Implement API call to fetch session details
      // const data = await getComputerUseSession(sessionId);
      // setSession(data);
      
      // For now, use setSession to avoid unused variable warning
      // setSession(null); 
      
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch session:', err);
      setError(err.message || 'Failed to load session');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSession();

    if (autoRefresh) {
      const interval = setInterval(fetchSession, refreshInterval);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [sessionId, autoRefresh, refreshInterval]);

  // Auto-scroll to latest step
  useEffect(() => {
    if (scrollRef.current && session?.status === 'running') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [session?.steps.length, session?.status]);

  const toggleStep = (stepId: string) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepId)) {
      newExpanded.delete(stepId);
    } else {
      newExpanded.add(stepId);
    }
    setExpandedSteps(newExpanded);
  };

  if (loading && !session) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-blue-600 animate-spin mb-4" />
        <p className="text-gray-500">{t('common.loading', 'Loading...')}</p>
      </div>
    );
  }

  if (error && !session) {
    return (
      <div className="p-6 text-center">
        <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <p className="text-red-600 mb-4">{error}</p>
        <Button onClick={fetchSession}>{t('common.retry', 'Retry')}</Button>
      </div>
    );
  }

  if (!session) return null;

  const progress = (session.current_round / session.max_rounds) * 100;

  return (
    <div className="w-full border rounded-xl bg-white shadow-sm overflow-hidden">
      <div className="p-4 border-b bg-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Monitor className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {t('computerUse.sessionMonitor', 'Computer Use Session')}
              </h3>
              <p className="text-sm text-gray-500">{session.task}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {getSessionStatusBadge(session.status, t)}
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <XCircle className="w-5 h-5 text-gray-400" />
            </button>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>
              {t('computerUse.round', 'Round')} {session.current_round} /{' '}
              {session.max_rounds}
            </span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-500" 
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 p-3 bg-gray-50 rounded-lg">
          <div className="text-center">
            <div className="text-2xl font-bold">{session.screenshots_count}</div>
            <div className="text-xs text-gray-500">
              {t('computerUse.screenshots', 'Screenshots')}
            </div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold">{session.actions_count}</div>
            <div className="text-xs text-gray-500">
              {t('computerUse.actions', 'Actions')}
            </div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">
              {session.errors_count}
            </div>
            <div className="text-xs text-gray-500">
              {t('computerUse.errors', 'Errors')}
            </div>
          </div>
        </div>

        {/* Error Message */}
        {session.error_message && (
          <div className="flex items-start gap-2 p-3 text-sm text-red-600 bg-red-50 rounded-lg">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{session.error_message}</span>
          </div>
        )}

        {/* Final Result */}
        {session.final_result && (
          <div className="p-3 bg-green-50 rounded-lg">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle className="w-4 h-4 text-green-600" />
              <span className="font-medium text-green-800">
                {t('computerUse.taskCompleted', 'Task Completed')}
              </span>
            </div>
            <p className="text-sm text-green-700">{session.final_result}</p>
          </div>
        )}

        {/* Steps Timeline */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium">
              {t('computerUse.executionHistory', 'Execution History')}
            </h4>
            <Button variant="ghost" onClick={fetchSession}>
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>

          <div className="h-64 pr-4 overflow-auto" ref={scrollRef}>
            <div className="space-y-2">
              {session.steps.length === 0 ? (
                <div className="py-8 text-center text-gray-500">
                  {session.status === 'running' ? (
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-6 h-6 animate-spin" />
                      <span>{t('computerUse.starting', 'Starting...')}</span>
                    </div>
                  ) : (
                    t('computerUse.noSteps', 'No execution steps yet')
                  )}
                </div>
              ) : (
                session.steps.map((step) => (
                  <div key={step.step_id} className="space-y-1">
                    <div
                      className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
                        step.status === 'running'
                          ? 'bg-blue-50'
                          : step.status === 'failed'
                          ? 'bg-red-50'
                          : 'hover:bg-gray-50'
                      }`}
                      onClick={() => toggleStep(step.step_id)}
                    >
                      <div className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-gray-100 text-xs font-medium">
                        {step.round_number}
                      </div>

                      {getStatusIcon(step.status)}

                      <div className="flex items-center gap-2">
                        {getActionIcon(step.action_type)}
                        <span className="text-sm font-medium capitalize">
                          {step.action_type || 'observe'}
                        </span>
                      </div>

                      {step.target_element && (
                        <span className="text-xs text-gray-500 truncate max-w-32">
                          {step.target_element}
                        </span>
                      )}

                      <div className="ml-auto flex items-center gap-2">
                        {step.duration_ms && (
                          <span className="text-xs text-gray-400">
                            {step.duration_ms}ms
                          </span>
                        )}
                        {expandedSteps.has(step.step_id) ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </div>
                    </div>

                    {expandedSteps.has(step.step_id) && (
                      <div className="ml-9 pl-3 border-l-2 border-gray-200 py-2 space-y-2">
                        {step.reasoning && (
                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              {t('computerUse.reasoning', 'Reasoning')}:
                            </span>
                            <p className="text-sm text-gray-700 mt-1">
                              {step.reasoning}
                            </p>
                          </div>
                        )}
                        {step.result && (
                          <div>
                            <span className="text-xs font-medium text-gray-500">
                              {t('computerUse.result', 'Result')}:
                            </span>
                            <p className="text-sm text-gray-700 mt-1">
                              {step.result}
                            </p>
                          </div>
                        )}
                        {step.screenshot_available && (
                          <Button variant="secondary">
                            <Image className="w-4 h-4 mr-1" />
                            {t('computerUse.viewScreenshot', 'View Screenshot')}
                          </Button>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Duration */}
        {session.started_at && (
          <div className="text-xs text-gray-500 text-right">
            {t('computerUse.started', 'Started')}:{' '}
            {new Date(session.started_at).toLocaleTimeString()}
            {session.completed_at && (
              <>
                {' | '}
                {t('computerUse.completed', 'Completed')}:{' '}
                {new Date(session.completed_at).toLocaleTimeString()}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default ComputerUseSessionMonitor;
