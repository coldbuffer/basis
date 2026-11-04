import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { EmptyState } from '@/components/app/shared/console/EmptyState.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import {
  workspaceOpenApiDELETE,
  workspaceOpenApiGET,
  workspaceOpenApiPOST,
  workspaceOpenApiPUT,
} from '@/lib/openapi/client.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { SqlCatalogEngineIcon } from '@/modules/workspace/sql-catalog/components/sql-catalog-engine-icon.js';
import {
  SqlCatalogSourceDialog,
  type SqlCatalogSourceDraft,
} from '@/modules/workspace/sql-catalog/components/sql-catalog-source-dialog.js';

const SCHEME_LABELS: Record<string, string> = {
  postgres: 'PostgreSQL',
  postgresql: 'PostgreSQL',
  mysql: 'MySQL',
  sqlite: 'SQLite',
  duckdb: 'DuckDB',
  clickhouse: 'ClickHouse',
  snowflake: 'Snowflake',
  databricks: 'Databricks',
  trino: 'Trino',
  kyuubi: 'Kyuubi',
  heavydb: 'HeavyDB',
};

type SqlCatalogSource = {
  source_id: string;
  display_name: string;
  scheme: string;
  connection_uri: string;
  extracted_at: string | null;
  counts: { tables: number; columns: number } | null;
};

type SnapshotBody = {
  snapshot: {
    counts: { tables: number; columns: number };
  };
};

type ApplyBody = {
  uri: string;
  classes: number;
  datatype_properties: number;
  object_properties: number;
};

export function SqlCatalogPanel({ workspaceId }: { workspaceId: string }) {
  const { t, locale } = useI18n();
  const copy = t.sql_catalog;
  const apiError = useApiErrorMessage();
  const { caps } = useWorkspaceCapabilities();
  const canWrite = !caps || caps.role !== 'viewer';
  const [sources, setSources] = useState<SqlCatalogSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<SqlCatalogSource | null>(null);
  const [applied, setApplied] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const body = await workspaceOpenApiGET<{ sources: SqlCatalogSource[] }>(
        workspaceId,
        'sql-catalog/sources',
      );
      setSources(body.sources);
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  }, [apiError, workspaceId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onTest(connectionUri: string) {
    await workspaceOpenApiPOST(workspaceId, 'sql-catalog/connection-test', {
      body: { connection_uri: connectionUri },
    });
  }

  async function onCreate(values: SqlCatalogSourceDraft) {
    setBusy('create');
    try {
      await workspaceOpenApiPUT(workspaceId, 'sql-catalog/sources/{source_id}', {
        params: { path: { source_id: values.sourceId } },
        body: {
          display_name: values.displayName,
          connection_uri: values.connectionUri,
          table_deny_regex: values.tableDenyRegex,
          table_allow_regex: values.tableAllowRegex,
          schemas: values.schemas,
        },
      });
      toast.success(copy.page.saved);
      setCreateOpen(false);
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(null);
    }
  }

  async function snapshot(source: SqlCatalogSource) {
    setBusy(`${source.source_id}:snapshot`);
    try {
      const body = await workspaceOpenApiPOST<SnapshotBody>(
        workspaceId,
        'sql-catalog/sources/{source_id}/snapshot',
        { params: { path: { source_id: source.source_id } } },
      );
      toast.success(
        fmt(copy.page.snapshot_done, {
          tables: body.snapshot.counts.tables,
          columns: body.snapshot.counts.columns,
        }),
      );
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(null);
    }
  }

  async function applyOntology(source: SqlCatalogSource) {
    setBusy(`${source.source_id}:apply`);
    try {
      const body = await workspaceOpenApiPOST<ApplyBody>(
        workspaceId,
        'sql-catalog/sources/{source_id}/ontology',
        { params: { path: { source_id: source.source_id } } },
      );
      setApplied((current) => ({ ...current, [source.source_id]: body.uri }));
      toast.success(
        fmt(copy.page.apply_done, {
          classes: body.classes,
          properties: body.datatype_properties + body.object_properties,
        }),
      );
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(null);
    }
  }

  async function remove(source: SqlCatalogSource) {
    setBusy(`${source.source_id}:delete`);
    try {
      await workspaceOpenApiDELETE(workspaceId, 'sql-catalog/sources/{source_id}', {
        params: { path: { source_id: source.source_id } },
      });
      setApplied((current) => {
        const next = { ...current };
        delete next[source.source_id];
        return next;
      });
      toast.success(copy.page.deleted);
      setPendingDelete(null);
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(null);
    }
  }

  const columns: DataTableColumn<SqlCatalogSource>[] = [
    {
      key: 'name',
      header: copy.page.col_name,
      render: (row) => (
        <div className="flex min-w-0 items-center gap-2">
          <SqlCatalogEngineIcon scheme={row.scheme} />
          <div className="min-w-0">
            <div className="truncate font-medium">{row.display_name}</div>
            <div className="truncate text-xs text-muted-foreground">
              {SCHEME_LABELS[row.scheme] ?? row.scheme}
            </div>
          </div>
        </div>
      ),
    },
    {
      key: 'connection',
      header: copy.page.col_connection,
      render: (row) => (
        <span className="block max-w-xs truncate font-mono text-xs" title={row.connection_uri}>
          {row.connection_uri}
        </span>
      ),
      hideBelow: 'md',
    },
    {
      key: 'snapshot',
      header: copy.page.col_snapshot,
      render: (row) =>
        row.extracted_at ? (
          <div className="flex min-w-0 flex-col items-start gap-1">
            <Badge variant="outline" className="badge-status-success">
              {row.counts
                ? fmt(copy.page.snapshot_summary, {
                    tables: row.counts.tables,
                    columns: row.counts.columns,
                  })
                : formatLocaleDateTime(locale as Locale, row.extracted_at)}
            </Badge>
            {row.counts ? (
              <span className="text-xs text-muted-foreground">
                {formatLocaleDateTime(locale as Locale, row.extracted_at)}
              </span>
            ) : null}
            {applied[row.source_id] ? (
              <span className="text-xs text-muted-foreground">{copy.page.applied_badge}</span>
            ) : null}
          </div>
        ) : (
          <Badge variant="outline">{copy.page.snapshot_none}</Badge>
        ),
      hideBelow: 'sm',
    },
    {
      key: 'actions',
      header: copy.page.col_actions,
      render: (row) => {
        const snapping = busy === `${row.source_id}:snapshot`;
        const applying = busy === `${row.source_id}:apply`;
        const captured = Boolean(row.extracted_at);
        return (
          <div className="flex flex-wrap items-center justify-end gap-1">
            {captured || applied[row.source_id] ? (
              <Button variant="link" size="sm" asChild>
                <Link to={workspacePath(workspaceId, 'ontology')}>{copy.page.open_ontology}</Link>
              </Button>
            ) : null}
            {canWrite ? (
              <>
                <Button
                  variant={captured ? 'outline' : 'default'}
                  size="sm"
                  data-testid={`sql-catalog-snapshot-${row.source_id}`}
                  disabled={busy !== null}
                  onClick={() => void snapshot(row)}
                >
                  {snapping ? <Spinner /> : null}
                  {captured ? copy.page.snapshot_again : copy.page.snapshot}
                </Button>
                {captured ? (
                  <Button
                    variant={applied[row.source_id] ? 'outline' : 'default'}
                    size="sm"
                    data-testid={`sql-catalog-apply-${row.source_id}`}
                    disabled={busy !== null}
                    onClick={() => void applyOntology(row)}
                  >
                    {applying ? <Spinner /> : null}
                    {copy.page.apply}
                  </Button>
                ) : null}
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground"
                  data-testid={`sql-catalog-delete-${row.source_id}`}
                  disabled={busy !== null}
                  onClick={() => setPendingDelete(row)}
                >
                  {copy.page.remove}
                </Button>
              </>
            ) : null}
          </div>
        );
      },
      align: 'right',
    },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3" data-testid="sql-catalog-panel">
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          {copy.page.refresh}
        </Button>
        {canWrite ? (
          <Button
            size="sm"
            data-testid="sql-catalog-add"
            onClick={() => setCreateOpen(true)}
          >
            {copy.page.add}
          </Button>
        ) : null}
      </div>
      {loading ? (
        <div className="flex justify-center py-14">
          <Spinner className="size-5" />
        </div>
      ) : sources.length === 0 ? (
        <EmptyState
          icon={<PublicIcon name="database" size={22} />}
          title={copy.page.empty}
          description={copy.page.empty_hint}
        />
      ) : (
        <DataTable columns={columns} data={sources} rowKey={(row) => row.source_id} />
      )}

      <SqlCatalogSourceDialog
        open={createOpen}
        busy={busy === 'create'}
        onOpenChange={setCreateOpen}
        onTest={async (connectionUri) => {
          try {
            await onTest(connectionUri);
          } catch (err) {
            toast.error(apiError(err));
            throw err;
          }
        }}
        onSubmit={onCreate}
      />

      <Dialog open={pendingDelete !== null} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.dialog.delete_title}</DialogTitle>
            <DialogDescription>{copy.dialog.delete_description}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPendingDelete(null)}>
              {copy.dialog.cancel}
            </Button>
            <Button
              type="button"
              data-testid="sql-catalog-confirm-delete"
              disabled={busy !== null}
              onClick={() => pendingDelete && void remove(pendingDelete)}
            >
              {copy.dialog.confirm_delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
