import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useI18n } from '@/i18n/context.js';
import { consumeWorkspaceAlertsStream, type WorkspaceAlertStreamItem } from '@/modules/workspace/alerts/lib/alerts-stream.js';
import { isSetupWorkspaceId, resolveSidebarWorkspaceId } from '@/lib/workspace/active-id.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { isWorkspaceScopedPath, parseWorkspaceIdFromPath } from '@/lib/nav/nav-config.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

function useWorkspaceAlertsTargetId(): string {
  const location = useLocation();
  const { workspaces } = useWorkspaceCatalog();
  const workspaceScoped = isWorkspaceScopedPath(location.pathname);
  const pathWorkspaceId = parseWorkspaceIdFromPath(location.pathname);
  const navWorkspaceId = resolveSidebarWorkspaceId(location.pathname, workspaces);
  return pathWorkspaceId && pathWorkspaceId !== 'all' && workspaceScoped ? pathWorkspaceId : navWorkspaceId;
}

/** Unread alert count for the active workspace, with live SSE updates. */
export function useWorkspaceUnreadAlerts(): number {
  const { locale } = useI18n();
  const alertsWorkspaceId = useWorkspaceAlertsTargetId();

  const [unreadCount, setUnreadCount] = useState(0);
  const [streamReady, setStreamReady] = useState(false);
  const streamSinceRef = useRef<string | undefined>(undefined);

  const refresh = useCallback(async () => {
    if (!alertsWorkspaceId || isSetupWorkspaceId(alertsWorkspaceId)) {
      setUnreadCount(0);
      return;
    }
    try {
      const data = await workspaceOpenApiGET<{ alerts: WorkspaceAlertStreamItem[]; unread_count: number }>(
        alertsWorkspaceId,
        'alerts',
        { params: { query: { limit: 1 } } },
      );
      const count =
        typeof data.unread_count === 'number' ? data.unread_count : data.alerts.length;
      setUnreadCount(count);
      streamSinceRef.current = data.alerts[0]?.created_at ?? new Date().toISOString();
      setStreamReady(true);
    } catch {
      /* non-blocking */
    }
  }, [alertsWorkspaceId]);

  useEffect(() => {
    setStreamReady(false);
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onChanged = () => {
      void refresh();
    };
    window.addEventListener('workspace-alerts-changed', onChanged);
    return () => window.removeEventListener('workspace-alerts-changed', onChanged);
  }, [refresh]);

  useEffect(() => {
    if (!alertsWorkspaceId || isSetupWorkspaceId(alertsWorkspaceId) || !streamReady) return;
    const ac = new AbortController();
    let backoff = 2000;
    let cancelled = false;

    const run = async () => {
      while (!cancelled && !ac.signal.aborted) {
        try {
          await consumeWorkspaceAlertsStream(alertsWorkspaceId, {
            since: streamSinceRef.current,
            signal: ac.signal,
            locale,
            onAlert: (alert) => {
              streamSinceRef.current = alert.created_at;
              setUnreadCount((count) => count + 1);
              window.dispatchEvent(new CustomEvent('workspace-alerts-changed'));
            },
          });
          backoff = 2000;
        } catch {
          if (ac.signal.aborted || cancelled) break;
          await new Promise((r) => window.setTimeout(r, backoff));
          backoff = Math.min(backoff * 2, 30_000);
        }
      }
    };
    void run();
    return () => {
      cancelled = true;
      ac.abort();
    };
  }, [streamReady, alertsWorkspaceId, locale]);

  return unreadCount;
}

/** Workspace id used for alerts deep links from the account menu. */
export function useWorkspaceAlertsNavId(): string {
  return useWorkspaceAlertsTargetId();
}
