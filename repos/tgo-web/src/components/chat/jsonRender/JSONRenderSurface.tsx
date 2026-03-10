import React, { useEffect, useMemo } from 'react';

import type { Spec, StateModel } from '@json-render/core';
import { ActionProvider, createStateStore, Renderer, StateProvider, useActions, VisibilityProvider } from '@json-render/react';

import { jsonRenderFallback, jsonRenderRegistry } from './registry';

/**
 * Syncs external handler map into ActionProvider's internal state.
 * ActionProvider only reads `handlers` prop on first mount (useState initial value).
 * During streaming the handler set grows as new action elements arrive,
 * so we call registerHandler() to keep ActionProvider in sync.
 */
const HandlerSync: React.FC<{
  handlers: Record<string, (params: Record<string, unknown>) => Promise<void>>;
}> = ({ handlers }) => {
  const { registerHandler } = useActions();
  useEffect(() => {
    for (const [name, fn] of Object.entries(handlers)) {
      registerHandler(name, fn);
    }
  }, [handlers, registerHandler]);
  return null;
};

interface JSONRenderSurfaceProps {
  spec: Spec | null;
  loading?: boolean;
  onSendMessage?: (message: string) => void;
}

const BUILTIN_ACTIONS = new Set(['setState', 'pushState', 'removeState', 'validateForm']);

function collectActionNames(spec: Spec | null): string[] {
  if (!spec) return [];

  const names = new Set<string>();
  for (const element of Object.values(spec.elements)) {
    if (!element) continue;
    const events = element.on;
    if (!events || typeof events !== 'object') continue;

    for (const binding of Object.values(events)) {
      if (Array.isArray(binding)) {
        for (const item of binding) {
          if (item && typeof item.action === 'string') {
            names.add(item.action);
          }
        }
        continue;
      }

      if (binding && typeof binding.action === 'string') {
        names.add(binding.action);
      }
    }
  }

  return Array.from(names).filter(n => !BUILTIN_ACTIONS.has(n));
}

function formatActionMessage(
  actionName: string,
  params?: Record<string, unknown>,
  state?: StateModel
): string {
  const parts: string[] = [`[${actionName}]`];
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== '') parts.push(`${k}: ${v}`);
    }
  }
  if (state) {
    for (const [k, v] of Object.entries(state)) {
      if (typeof v === 'object' && v !== null) {
        for (const [fk, fv] of Object.entries(v as Record<string, unknown>)) {
          if (fv != null && fv !== '') parts.push(`${fk}: ${fv}`);
        }
      } else if (v != null && v !== '') {
        parts.push(`${k}: ${v}`);
      }
    }
  }
  return parts.join('\n');
}

export const JSONRenderSurface: React.FC<JSONRenderSurfaceProps> = ({ spec, loading, onSendMessage }) => {
  const stateKey = useMemo(() => JSON.stringify(spec?.state ?? {}), [spec?.state]);

  const store = useMemo(() => createStateStore(spec?.state ?? {}), [stateKey]);

  const actionHandlers = useMemo(() => {
    const handlers: Record<string, (params: Record<string, unknown>) => Promise<void>> = {};
    for (const actionName of collectActionNames(spec)) {
      handlers[actionName] = async (params: Record<string, unknown>) => {
        // Contains statePath → treat as state update, not a submit action
        if (params?.statePath && typeof params.statePath === 'string') {
          store.set(params.statePath, params.value);
          return;
        }
        // Send as formatted text message via onSendMessage
        if (!onSendMessage) return;
        onSendMessage(formatActionMessage(actionName, params, store.getSnapshot()));
      };
    }
    return handlers;
  }, [spec, onSendMessage, store]);

  if (!spec) return null;

  return (
    <div className="json-render-surface mt-2 space-y-3">
      <StateProvider key={stateKey} store={store}>
        <VisibilityProvider>
          <ActionProvider handlers={actionHandlers}>
            <HandlerSync handlers={actionHandlers} />
            <Renderer spec={spec} registry={jsonRenderRegistry} loading={loading} fallback={jsonRenderFallback} />
          </ActionProvider>
        </VisibilityProvider>
      </StateProvider>
    </div>
  );
};
