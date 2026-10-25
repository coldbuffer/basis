import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { GraphAuditEventLinks } from '@/modules/graph/components/graph-audit-event-links.js';
import {
  formatGraphAuditAction,
  formatGraphAuditDetail,
  type GraphAuditEvent,
} from '@/modules/graph/lib/graph-audit.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { workspaceReviewPath } from '@/lib/nav/nav-config.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { formatLocaleDateTime } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';

export function GraphAuditRecent({
  workspaceId,
  limit = 15,
  actionPrefix = 'workspace.graph.',
  refreshKey = 0,
}: {
  workspaceId: string;
  limit?: number;
  actionPrefix?: string;
  refreshKey?: number;
}) {
  const { t, locale } = useI18n();
  const { isAdmin } = useBasisSession();
  const w = t.graph.canvas.widgets;
  const platformAuditHref = `/admin/audit?${new URLSearchParams({
    workspace_id: workspaceId,
    action_prefix: actionPrefix,
  }).toString()}`;
  const [events, setEvents] = useState<GraphAuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await workspaceOpenApiGET<{ events: GraphAuditEvent[] }>(
        workspaceId,
        'audit/graph-mutations',
        { params: { query: { limit, action_prefix: actionPrefix } } },
      );
      setEvents(body.events ?? []);
    } catch (err) {
      setError(formatUserFacingApiError(err, locale));
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [actionPrefix, workspaceId, limit, locale]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  return (
    <div className="space-y-3 border-t border-border pt-4">
      <h3 className="text-sm font-medium">{w.audit_title}</h3>
      <p className="text-xs text-muted-foreground">{w.audit_description}</p>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" />
          {t.core.common.loading}
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : events.length === 0 ? (
        <p className="text-sm text-muted-foreground">{w.audit_empty}</p>
      ) : (
        <>
          <ul className="divide-y divide-border rounded-md border border-border text-sm">
            {events.map((event) => (
              <li
                key={event.id}
                className="flex flex-col gap-1 px-3 py-2.5 sm:flex-row sm:items-start sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium">
                    {formatGraphAuditAction(event.action, locale)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {formatGraphAuditDetail(event, locale) || t.core.common.emptyCell}
                  </div>
                  <GraphAuditEventLinks workspaceId={workspaceId} detail={event.detail} />
                </div>
                <time className="shrink-0 text-xs text-muted-foreground">
                  {formatLocaleDateTime(locale as Locale, event.created_at)}
                </time>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <Link
              to={workspaceReviewPath(workspaceId)}
              className="inline-block text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              data-testid="graph-audit-open-review"
            >
              {t.graph.import_export.open_review_queue}
            </Link>
            {isAdmin ? (
              <Link
                to={platformAuditHref}
                className="inline-block text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                data-testid="graph-audit-open-platform-audit"
              >
                {w.audit_open_platform}
              </Link>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
