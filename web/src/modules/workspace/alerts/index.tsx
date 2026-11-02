import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  ConsolePageLayout,
  DataPanel,
  DataPanelBody,
  DataPanelToolbar,
  EmptyState,
} from '@/components/app/shared/console/index.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { formatLocaleDateTime } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { alertKindLabel, alertSeverityLabel } from '@/modules/workspace/alerts/lib/alert-labels.js';
import { workspaceAlertAction } from '@/modules/workspace/alerts/lib/alert-actions.js';
import { alertActionLabel } from '@/modules/workspace/alerts/lib/alert-action-label.js';
import { groupAlertsByEpisode, alertDetailLines } from '@/modules/workspace/alerts/lib/alert-detail.js';
import { consumeWorkspaceAlertsStream, type WorkspaceAlertStreamItem } from '@/modules/workspace/alerts/lib/alerts-stream.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspaceAlertsPath, parseKbAlertsUrlState } from '@/modules/workspace/alerts/lib/alerts-url.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { cn } from '@/lib/utils.js';
import { workspaceOpenApiGET, workspaceOpenApiPOST } from '@/lib/openapi/client.js';

type AlertsResponse = {
  alerts: WorkspaceAlertStreamItem[];
  unread_count: number;
};

function severityBadgeProps(severity: string): {
  variant: 'destructive' | 'outline' | 'secondary';
  className?: string;
} {
  const normalized = severity.toLowerCase();
  if (normalized === 'critical' || normalized === 'error' || normalized === 'high') {
    return { variant: 'destructive' };
  }
  if (normalized === 'warning' || normalized === 'warn' || normalized === 'medium') {
    return { variant: 'outline', className: 'badge-status-warning' };
  }
  return { variant: 'secondary' };
}

export function AlertsPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const highlightEpisodeKey = parseKbAlertsUrlState(searchParams.toString()).episodeKey;
  const { t, locale } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const [alerts, setAlerts] = useState<WorkspaceAlertStreamItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [streamReady, setStreamReady] = useState(false);
  const streamSinceRef = useRef<string | undefined>(undefined);

  const notifyBadgeSync = useCallback(() => {
    window.dispatchEvent(new CustomEvent('workspace-alerts-changed'));
  }, []);

  const mergeAlert = useCallback(
    (alert: WorkspaceAlertStreamItem) => {
      setAlerts((prev) => {
        if (prev.some((a) => a.id === alert.id)) return prev;
        return [alert, ...prev].slice(0, 100);
      });
      notifyBadgeSync();
    },
    [notifyBadgeSync],
  );

  const refresh = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await workspaceOpenApiGET<AlertsResponse>(id, 'alerts', {
        params: { query: { limit: 100 } },
      });
      setAlerts(data.alerts);
      streamSinceRef.current = data.alerts[0]?.created_at ?? new Date().toISOString();
      setStreamReady(true);
      if (data.unread_count > 0) {
        await workspaceOpenApiPOST(id, 'alerts/mark-all-read');
        setAlerts((prev) =>
          prev.map((a) => (a.read_at ? a : { ...a, read_at: new Date().toISOString() })),
        );
      }
      notifyBadgeSync();
    } catch {
      /* non-blocking */
    } finally {
      setLoading(false);
    }
  }, [id, notifyBadgeSync]);

  useEffect(() => {
    if (!id) return;
    setStreamReady(false);
    void refresh();
  }, [id, refresh]);

  useEffect(() => {
    if (!id || !streamReady) return;
    const ac = new AbortController();
    let backoff = 2000;
    let cancelled = false;

    const run = async () => {
      while (!cancelled && !ac.signal.aborted) {
        try {
          await consumeWorkspaceAlertsStream(id, {
            since: streamSinceRef.current,
            signal: ac.signal,
            locale,
            onAlert: (alert) => {
              streamSinceRef.current = alert.created_at;
              mergeAlert(alert);
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
  }, [id, locale, mergeAlert, streamReady]);

  const dismiss = async (alertId: string) => {
    if (!id) return;
    try {
      await workspaceOpenApiPOST(id, `alerts/${alertId}/dismiss`);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
      notifyBadgeSync();
    } catch {
      /* ignore */
    }
  };

  const dismissAll = async () => {
    if (!id || alerts.length === 0) return;
    try {
      await workspaceOpenApiPOST<{ dismissed_count: number; unread_count: number }>(
        id,
        'alerts/dismiss-all',
      );
      setAlerts([]);
      notifyBadgeSync();
    } catch {
      /* ignore */
    }
  };

  const copyEpisodeLink = async (episodeKey: string) => {
    if (!id) return;
    const url = `${window.location.origin}${workspaceAlertsPath(id, { episodeKey })}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success(t.core.common.copySuccess);
    } catch {
      toast.error(t.core.common.copy);
    }
  };

  useEffect(() => {
    if (!id || !highlightEpisodeKey || loading) return;
    const el = document.querySelector(
      `[data-alert-episode="${CSS.escape(highlightEpisodeKey)}"]`,
    );
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [highlightEpisodeKey, id, loading, alerts.length]);

  if (!id) return null;
  const kbName = getWorkspace(id)?.name ?? id;
  const alertGroups = groupAlertsByEpisode(alerts);

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: kbName, to: workspacePath(id, 'graph') },
        { label: t.alerts.menu.alerts },
      ]}
      subtitle={t.alerts.page.subtitle}
      actions={
        <div className="flex items-center gap-2">
          {alerts.length > 0 ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              data-testid="alerts-dismiss-all"
              onClick={() => void dismissAll()}
            >
              <PublicIcon name='checks' className="mr-1.5 size-3.5" />
              {t.alerts.page.dismiss_all}
            </Button>
          ) : null}
          <Button type="button" variant="outline" size="sm" asChild>
            <Link
              to={`${workspacePath(id, 'integration')}?tab=openapi`}
              data-testid="workspace-alerts-openapi-link"
            >
              {t.alerts.page.api_docs_link}
            </Link>
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={loading}
            onClick={() => void refresh()}
          >
            <PublicIcon name='arrow-refresh-01' className={`mr-1.5 size-3.5 ${loading ? 'animate-spin' : ''}`} />
            {t.alerts.page.refresh}
          </Button>
        </div>
      }
    >
      <DataPanel>
        <DataPanelToolbar
          search={
            <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
              <span>{t.alerts.page.alerts_title}</span>
              {alerts.length > 0 ? (
                <Badge variant="secondary" className="tabular-nums">
                  {alerts.length}
                </Badge>
              ) : null}
              {streamReady && !loading ? (
                <Badge
                  variant="outline"
                  className="border-ok/40 bg-ok-soft text-ok"
                  data-testid="alerts-stream-live"
                >
                  {t.alerts.page.stream_live}
                </Badge>
              ) : null}
            </div>
          }
        />
        <DataPanelBody>
          {loading && alerts.length === 0 ? (
            <div className="flex items-center justify-center py-14">
              <Spinner />
            </div>
          ) : alerts.length === 0 ? (
            <EmptyState
              icon={<PublicIcon name='bell-01' className="size-5 text-muted-foreground" />}
              title={t.alerts.page.alerts_empty}
              description={t.alerts.page.subtitle}
            />
          ) : (
            <div className="divide-y divide-border" aria-label={t.alerts.page.episode_group_aria}>
              {alertGroups.map((group) => (
                <section
                  key={group.episodeKey}
                  data-alert-episode={group.episodeKey}
                  data-testid={`alerts-episode-${group.episodeKey}`}
                  className={cn(
                    highlightEpisodeKey === group.episodeKey &&
                      'ring-2 ring-inset ring-primary/40',
                  )}
                >
                  <div className="flex items-center gap-2 border-b border-border/60 bg-muted/20 px-4 py-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {alertKindLabel(t.alerts.page, group.kind)}
                    </span>
                    <Badge variant="outline" className="h-5 tabular-nums text-[10px]">
                      {group.alerts.length}
                    </Badge>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="ml-auto h-7 px-2 text-xs"
                      aria-label={t.alerts.page.copy_episode_aria}
                      data-testid={`alerts-copy-episode-link-${group.episodeKey}`}
                      onClick={() => void copyEpisodeLink(group.episodeKey)}
                    >
                      {t.alerts.page.copy_episode_link}
                    </Button>
                  </div>
                  <ul className="divide-y divide-border">
                    {group.alerts.map((alert) => {
                      const action = workspaceAlertAction(id, alert);
                      const detailLines = alertDetailLines(t.alerts.page, alert);
                      return (
                        <li
                          key={alert.id}
                          className={`flex items-start justify-between gap-4 px-4 py-3.5 transition-colors hover:bg-muted/30 ${alert.read_at ? 'opacity-80' : ''}`}
                        >
                          <div className="min-w-0 flex-1 space-y-1.5">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge {...severityBadgeProps(alert.severity)}>
                                {alertSeverityLabel(t.alerts.page, alert.severity)}
                              </Badge>
                              <time className="text-xs text-muted-foreground tabular-nums">
                                {formatLocaleDateTime(locale as Locale, alert.created_at)}
                              </time>
                            </div>
                            <p className="text-sm font-medium leading-snug text-foreground">
                              {alert.message}
                            </p>
                            {detailLines.length > 0 ? (
                              <ul className="space-y-0.5 text-xs text-muted-foreground">
                                {detailLines.map((line) => (
                                  <li key={line}>{line}</li>
                                ))}
                              </ul>
                            ) : null}
                            {action ? (
                              <div>
                                <Link
                                  to={action.href}
                                  className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                                >
                                  {alertActionLabel(t.alerts.page, action.labelKey)}
                                  <PublicIcon name="link-external" className="size-3" />
                                </Link>
                              </div>
                            ) : null}
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="size-7 shrink-0 text-muted-foreground hover:text-foreground"
                            aria-label={t.alerts.page.dismiss_aria}
                            onClick={() => void dismiss(alert.id)}
                          >
                            <PublicIcon name="x-02" className="size-4" />
                          </Button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </DataPanelBody>
      </DataPanel>
    </ConsolePageLayout>
  );
}
