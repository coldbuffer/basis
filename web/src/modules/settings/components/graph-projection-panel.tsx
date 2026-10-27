import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { ImportExportDialog } from '@/components/app/shared/workspace/import-export/import-export-dialog.js';
import { GraphAuditRecent } from './graph-audit-recent.js';
import { GraphRebuildButton } from '@/components/app/shared/workspace/graph-rebuild-button.js';
import { Button } from '@/components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { graphProjectionStatusLabel } from '@/modules/settings/lib/graph-projection-labels.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { formatUserFacingApiError, messageForApiErrorCode } from '@/lib/errors/api-error-message.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

type GraphProjectionStatus = {
  revision: number;
  schema_version: number;
  status: string;
  last_built_at: string | null;
  last_error_code: string | null;
  node_count?: number;
  edge_count?: number;
};

export function GraphProjectionPanel({
  workspaceId,
  canRebuild,
  graphEnabled,
}: {
  workspaceId: string;
  canRebuild: boolean;
  graphEnabled: boolean;
}) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const p = t.graph.projection;
  const emptyCell = t.core.common.emptyCell;
  const { isAdmin } = useBasisSession();
  const auditGraphUrl = `/admin/audit?workspace_id=${encodeURIComponent(workspaceId)}&action_prefix=${encodeURIComponent('workspace.graph.')}`;
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<GraphProjectionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [auditRefreshKey, setAuditRefreshKey] = useState(0);
  const [exportOpen, setExportOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!graphEnabled) {
      setStatus(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const body = await workspaceOpenApiGET<GraphProjectionStatus>(workspaceId, 'graph/projection');
      setStatus(body);
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }, [graphEnabled, workspaceId, locale]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!graphEnabled) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{p.title}</CardTitle>
          <CardDescription>{p.unavailable_desc}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="text-base">{p.title}</CardTitle>
          <CardDescription>{p.description}</CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" asChild>
            <Link to={workspacePath(workspaceId, 'graph')}>{p.open_graph}</Link>
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            data-testid="workspace-settings-export-graph"
            onClick={() => setExportOpen(true)}
          >
            {p.export_graph}
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground" data-testid="workspace-settings-export-api-hint">
          {p.export_api_hint}{' '}
          <Link
            to={`${workspacePath(workspaceId, 'integration')}?tab=openapi`}
            className="text-primary hover:underline"
          >
            {p.export_api_link}
          </Link>{' '}
          {p.export_api_suffix}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" />
            {t.core.common.loading}
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : status ? (
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">{p.ledger_revision}</dt>
              <dd className="font-mono font-medium">{formatLocaleNumber(loc, status.revision)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{p.projection_status}</dt>
              <dd className="font-medium">{graphProjectionStatusLabel(p, status.status)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{p.nodes_edges}</dt>
              <dd className="font-mono">
                {fmt(p.nodes_edges_value, {
                  nodes:
                    status.node_count != null
                      ? formatLocaleNumber(loc, status.node_count)
                      : emptyCell,
                  edges:
                    status.edge_count != null
                      ? formatLocaleNumber(loc, status.edge_count)
                      : emptyCell,
                })}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">{p.last_built}</dt>
              <dd>
                {status.last_built_at
                  ? formatLocaleDateTime(loc, status.last_built_at)
                  : emptyCell}
              </dd>
            </div>
            {status.last_error_code ? (
              <div className="sm:col-span-2">
                <dt className="text-muted-foreground">{p.last_error}</dt>
                <dd className="text-destructive">
                  {messageForApiErrorCode(status.last_error_code, locale as Locale) ??
                    status.last_error_code}
                </dd>
              </div>
            ) : null}
          </dl>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
          {canRebuild ? (
            <GraphRebuildButton
              workspaceId={workspaceId}
              onRebuilt={() => {
                void refresh();
                setAuditRefreshKey((key) => key + 1);
              }}
            />
          ) : (
            <p className="text-xs text-muted-foreground">{p.editor_required}</p>
          )}
          <p className="text-xs text-muted-foreground">
            {p.audit_note}
            {isAdmin ? (
              <>
                {' '}
                <Link className="text-primary hover:underline" to={auditGraphUrl}>
                  {p.view_audit_graph}
                </Link>
              </>
            ) : null}
          </p>
        </div>

        <GraphAuditRecent workspaceId={workspaceId} refreshKey={auditRefreshKey} />
      </CardContent>
      <ImportExportDialog
        workspaceId={workspaceId}
        open={exportOpen}
        onOpenChange={setExportOpen}
        focus="export"
      />
    </Card>
  );
}
