import { type FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  DataPanel,
  DataPanelBody,
  DataPanelTableFooter,
  DataPanelToolbar,
  EmptyState,
  ToolbarSearch,
} from '@/components/app/shared/console/index.js';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { EntityRefLine } from '@/components/app/shared/workspace/entity-ref-line.js';
import { DerivedFactCard } from '@/components/app/shared/workspace/derived-fact-card.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { Input } from '@/components/ui/input.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { ledgerStatementStatusLabel } from '@/modules/library/lib/ledger-labels.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { reviewItemPath } from '@/modules/review/lib/review-url-state.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { workspaceOpenApiDELETE, workspaceOpenApiGET, workspaceOpenApiPOST } from '@/lib/openapi/client.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';

const ENTITY_PAGE_SIZE = 10;

export type LedgerEntityHit = {
  id?: string;
  entity_id: string;
  canonical_label: string | null;
  description: string | null;
  entity_kind: string;
};

type EntityDeleteStatement = {
  statement_id: string;
  subject_id: string;
  subject_label: string | null;
  surface_phrase: string;
  object_entity_id: string | null;
  object_label: string | null;
  object_value: string | null;
  status: string;
  evidence_quote: string | null;
};

type EntityDeletePreview = {
  entity_id: string;
  canonical_label: string | null;
  statement_count: number;
  statements_truncated: boolean;
  statements: EntityDeleteStatement[];
  typed_fact_count: number;
  derived_fact_count: number;
  merge_count: number;
};

function statementDeleteLine(statement: EntityDeleteStatement): string {
  const subject = statement.subject_label || statement.subject_id;
  const object = statement.object_entity_id
    ? statement.object_label || statement.object_entity_id
    : statement.object_value || '';
  return `${subject} ${statement.surface_phrase} ${object}`.trim();
}

type EntityFactHit = {
  statement_id: string;
  surface_phrase: string;
  object_entity_id: string | null;
  object_value: string | null;
  status: string;
  evidence_chunk_id?: string | null;
  evidence_quote?: string | null;
};

type DerivedFactHit = {
  id: string;
  predicate_uri: string;
  subject_id: string;
  object_entity_id: string | null;
  object_value: string | null;
  recorded_at?: string | null;
  rule_id: string | null;
  derivations: Array<{ premise_kind: string; premise_id: string }>;
};

type EntityExternalSyncDto = {
  ref_id: string;
  mapping_id: string;
  provider: string;
  stream_name: string;
  external_table: string;
  external_pk: string;
  sync_direction: string;
  writeback_mode: string;
  writable_columns: Array<{
    column: string;
    surface_phrase: string;
    predicate_uri: string;
    current_value: string | null;
  }>;
};

export function ledgerEntityId(hit: LedgerEntityHit): string {
  return hit.id ?? hit.entity_id;
}

function EntityFactsPanel({
  workspaceId,
  entityId,
  highlightStatementId,
}: {
  workspaceId: string;
  entityId: string;
  highlightStatementId?: string;
}) {
  const { t, locale } = useI18n();
  const l = t.entities.ledger;
  const apiError = useApiErrorMessage();
  const [entityFacts, setEntityFacts] = useState<EntityFactHit[]>([]);
  const [entityDerivedFacts, setEntityDerivedFacts] = useState<DerivedFactHit[]>([]);
  const [externalSync, setExternalSync] = useState<EntityExternalSyncDto | null>(null);
  const [writebackValues, setWritebackValues] = useState<Record<string, string>>({});
  const [proposingWriteback, setProposingWriteback] = useState(false);
  const [queuedReviewItemId, setQueuedReviewItemId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const factLabelIds = entityFacts.flatMap((fact) =>
    fact.object_entity_id ? [fact.object_entity_id] : [],
  );
  const factLabels = useWorkspaceNodeLabels(workspaceId, [entityId, ...factLabelIds]);

  const loadEntityFacts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await workspaceOpenApiGET<{
        facts: EntityFactHit[];
        derived_facts?: DerivedFactHit[];
        external_sync?: EntityExternalSyncDto | null;
      }>(workspaceId, `ledger/entities/${encodeURIComponent(entityId)}/facts`);
      setEntityFacts(data.facts ?? []);
      setEntityDerivedFacts(data.derived_facts ?? []);
      const ext = data.external_sync ?? null;
      setExternalSync(ext);
      if (ext?.writable_columns) {
        const initial: Record<string, string> = {};
        for (const col of ext.writable_columns) {
          initial[col.column] = col.current_value ?? '';
        }
        setWritebackValues(initial);
      }
    } catch {
      setEntityFacts([]);
      setEntityDerivedFacts([]);
      setExternalSync(null);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, entityId]);

  useEffect(() => {
    void loadEntityFacts();
  }, [loadEntityFacts]);

  async function handleProposeWriteback() {
    if (!externalSync) return;
    setProposingWriteback(true);
    setQueuedReviewItemId(null);
    try {
      const res = await workspaceOpenApiPOST<{
        outbox_id: string;
        status: string;
        review_item_id?: string | null;
      }>(workspaceId, 'connectors/outbox/propose', {
        body: {
          entity_id: entityId,
          field_updates: writebackValues,
        },
      });
      if (res.review_item_id) {
        setQueuedReviewItemId(res.review_item_id);
      } else {
        toast.success(l.writeback_applied_toast);
        await loadEntityFacts();
      }
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setProposingWriteback(false);
    }
  }

  useEffect(() => {
    if (!highlightStatementId || loading) return;
    const el = document.getElementById(`ledger-statement-${highlightStatementId}`);
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [highlightStatementId, loading, entityFacts]);

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner className="size-5" />
      </div>
    );
  }

  if (entityFacts.length === 0 && entityDerivedFacts.length === 0 && !externalSync) {
    return (
      <p className="text-sm text-muted-foreground">
        {l.no_statements_or_derived}
      </p>
    );
  }

  return (
    <div className="max-h-[min(60vh,28rem)] space-y-5 overflow-y-auto pr-1">
      {externalSync ? (
        <section
          className="rounded-lg border border-border/80 bg-muted/30 p-3"
          data-testid="entity-external-sync-section"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              {l.external_sync_section}
            </h4>
            <Badge variant="outline" className="font-mono text-[11px]">
              {externalSync.provider} · {externalSync.external_table} ({externalSync.external_pk})
            </Badge>
          </div>
          {externalSync.sync_direction === 'bidirectional' &&
          externalSync.writeback_mode !== 'disabled' &&
          externalSync.writable_columns.length > 0 ? (
            <div className="mt-3 space-y-2.5">
              {externalSync.writable_columns.map((col) => (
                <div key={col.column} className="flex items-center gap-2 text-xs">
                  <span className="w-28 shrink-0 font-mono font-medium text-foreground">
                    {col.column}
                  </span>
                  <Input
                    value={writebackValues[col.column] ?? ''}
                    onChange={(e) =>
                      setWritebackValues((prev) => ({
                        ...prev,
                        [col.column]: e.target.value,
                      }))
                    }
                    className="h-7 font-mono text-xs"
                    data-testid={`writeback-input-${col.column}`}
                  />
                </div>
              ))}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                {queuedReviewItemId ? (
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-muted-foreground">{l.writeback_review_queued}</span>
                    <Button variant="link" size="sm" className="h-auto p-0 text-xs" asChild>
                      <Link
                        to={reviewItemPath(workspaceId, queuedReviewItemId)}
                        data-testid="open-writeback-review-link"
                      >
                        {l.open_review_queue}
                      </Link>
                    </Button>
                  </div>
                ) : (
                  <span />
                )}
                <Button
                  size="sm"
                  variant="outline"
                  disabled={proposingWriteback}
                  onClick={() => void handleProposeWriteback()}
                  data-testid="propose-entity-writeback-btn"
                >
                  {proposingWriteback ? l.proposing_writeback : l.propose_writeback_button}
                </Button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}
      {entityFacts.length > 0 ? (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              {l.statements_section}
            </h4>
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {formatLocaleNumber(locale as Locale, entityFacts.length)}
            </span>
          </div>
          <ul className="space-y-2">
            {entityFacts.map((fact) => (
              <li
                key={fact.statement_id}
                id={`ledger-statement-${fact.statement_id}`}
                data-testid="ledger-statement-row"
                className={`rounded-lg border border-border/70 bg-bg-3/50 p-3${
                  highlightStatementId === fact.statement_id ? ' ring-2 ring-primary' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-medium">{fact.surface_phrase}</span>
                  <Badge variant="secondary">
                    {ledgerStatementStatusLabel(l, fact.status)}
                  </Badge>
                </div>
                <div className="mt-2 flex items-start gap-1.5 text-sm">
                  <PublicIcon name="arrow-right" size={14} className="mt-0.5 shrink-0 text-muted-foreground" />
                  {fact.object_entity_id ? (
                    <EntityRefLine id={fact.object_entity_id} labels={factLabels} className="min-w-0" />
                  ) : (
                    <span className="text-muted-foreground">{fact.object_value}</span>
                  )}
                </div>
                {fact.evidence_quote ? (
                  <blockquote className="mt-2 border-l-2 border-border pl-2 text-xs leading-relaxed text-muted-foreground">
                    {fact.evidence_quote}
                  </blockquote>
                ) : null}
                {fact.evidence_chunk_id ? (
                  <div className="mt-2 flex flex-wrap gap-3">
                    <Button variant="link" size="sm" className="h-auto p-0 text-xs" asChild>
                      <Link
                        to={`${workspacePath(workspaceId, 'sources')}?chunk=${encodeURIComponent(fact.evidence_chunk_id)}`}
                      >
                        {l.open_evidence}
                      </Link>
                    </Button>
                    <Button variant="link" size="sm" className="h-auto p-0 text-xs" asChild>
                      <Link to={`${workspacePath(workspaceId, 'search')}?entity=${encodeURIComponent(entityId)}`}>
                        {l.search_chunks}
                      </Link>
                    </Button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {entityDerivedFacts.length > 0 ? (
        <section>
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              {l.derived_section}
            </h4>
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {formatLocaleNumber(locale as Locale, entityDerivedFacts.length)}
            </span>
          </div>
          <ul className="space-y-2">
            {entityDerivedFacts.map((df) => (
              <DerivedFactCard key={df.id} workspaceId={workspaceId} fact={df} labels={factLabels} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

export function LedgerEntityList({
  workspaceId,
  entities,
  emptyLabel,
}: {
  workspaceId: string;
  entities: LedgerEntityHit[];
  emptyLabel: string;
}) {
  const { t } = useI18n();
  const l = t.entities.ledger;
  const { caps } = useWorkspaceCapabilities();
  const [factsEntityId, setFactsEntityId] = useState<string | null>(null);
  const showLineage = Boolean(caps?.provenance && caps?.graph);

  if (entities.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyLabel}</p>;
  }

  return (
    <div className="space-y-3">
      {entities.map((hit) => {
        const entityId = ledgerEntityId(hit);
        const labels: Record<string, string | null> = {
          [entityId]: hit.canonical_label,
        };
        const factsOpen = factsEntityId === entityId;
        return (
          <div key={entityId} className="rounded-md border p-3 text-sm">
            <div className="flex items-start justify-between gap-2">
              <EntityRefLine id={entityId} labels={labels} />
              <div className="flex shrink-0 flex-col gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setFactsEntityId(factsOpen ? null : entityId)}
                >
                  {factsOpen ? l.hide_statements : l.show_statements}
                </Button>
                <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                  <Link to={`${workspacePath(workspaceId, 'graph')}?focus=${encodeURIComponent(entityId)}`}>
                    {l.open_in_graph}
                  </Link>
                </Button>
                {showLineage ? (
                  <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
                    <Link to={`${workspacePath(workspaceId, 'lineage')}?node=${encodeURIComponent(entityId)}`}>
                      {l.open_lineage}
                    </Link>
                  </Button>
                ) : null}
              </div>
            </div>
            {hit.description ? (
              <p className="mt-2 line-clamp-2 text-muted-foreground">{hit.description}</p>
            ) : null}
            <div className="mt-1 text-xs text-muted-foreground">{hit.entity_kind}</div>
            {factsOpen ? (
              <div className="mt-3 border-t border-border pt-3">
                <EntityFactsPanel workspaceId={workspaceId} entityId={entityId} />
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function LedgerEntityBrowser({
  workspaceId,
  loadRecentOnMount = true,
  focusStatementId,
}: {
  workspaceId: string;
  limit?: number;
  loadRecentOnMount?: boolean;
  focusStatementId?: string;
}) {
  const { t, locale } = useI18n();
  const l = t.entities.ledger;
  const emptyCell = t.core.common.emptyCell;
  const { caps } = useWorkspaceCapabilities();
  const apiError = useApiErrorMessage();
  const canDeleteEntity = ['owner', 'admin', 'editor'].includes(caps?.role ?? '');
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [entities, setEntities] = useState<LedgerEntityHit[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [factsTarget, setFactsTarget] = useState<LedgerEntityHit | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<LedgerEntityHit | null>(null);
  const [deletePreview, setDeletePreview] = useState<EntityDeletePreview | null>(null);
  const [highlightStatementId, setHighlightStatementId] = useState<string | undefined>(undefined);
  const [deletePreviewError, setDeletePreviewError] = useState<string | null>(null);
  const [deletePreviewLoading, setDeletePreviewLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [invalidateTarget, setInvalidateTarget] = useState<LedgerEntityHit | null>(null);
  const [invalidating, setInvalidating] = useState(false);

  const showLineage = Boolean(caps?.provenance && caps?.graph);

  const totalPages = Math.max(1, Math.ceil(total / ENTITY_PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageStart = total === 0 ? 0 : (safePage - 1) * ENTITY_PAGE_SIZE + 1;
  const pageEnd = Math.min(safePage * ENTITY_PAGE_SIZE, total);

  const loc = locale as Locale;
  const countLabel =
    total === 0
      ? l.entity_count_empty
      : fmt(l.entity_count, {
          start: formatLocaleNumber(loc, pageStart),
          end: formatLocaleNumber(loc, pageEnd),
          total: formatLocaleNumber(loc, total),
        });

  const labelIds = entities.map((hit) => ledgerEntityId(hit));
  const nodeLabels = useWorkspaceNodeLabels(workspaceId, labelIds);

  const fetchEntities = useCallback(
    async (q: string, pageIndex: number) => {
      setLoading(true);
      setError(null);
      try {
        const offset = (pageIndex - 1) * ENTITY_PAGE_SIZE;
        const query: Record<string, unknown> = {
          limit: ENTITY_PAGE_SIZE,
          offset,
        };
        if (q.trim()) query.query = q.trim();
        const data = await workspaceOpenApiGET<{
          entities: LedgerEntityHit[];
          total: number;
        }>(workspaceId, 'ledger/entities', { params: { query } });
        setEntities(data.entities ?? []);
        setTotal(data.total ?? 0);
      } catch (err) {
        setError(apiError(err));
        setEntities([]);
        setTotal(0);
      } finally {
        setLoading(false);
      }
    },
    [apiError, workspaceId],
  );

  useEffect(() => {
    if (!loadRecentOnMount) return;
    void fetchEntities(appliedQuery, safePage);
  }, [appliedQuery, fetchEntities, loadRecentOnMount, safePage]);

  useEffect(() => {
    if (!deleteTarget) {
      setDeletePreview(null);
      setDeletePreviewError(null);
      return;
    }
    const entityId = ledgerEntityId(deleteTarget);
    let cancelled = false;
    setDeletePreview(null);
    setDeletePreviewError(null);
    setDeletePreviewLoading(true);
    void (async () => {
      try {
        const preview = await workspaceOpenApiGET<EntityDeletePreview>(
          workspaceId,
          `ledger/entities/${encodeURIComponent(entityId)}/delete-preview`,
        );
        if (!cancelled) setDeletePreview(preview);
      } catch (err) {
        if (!cancelled) setDeletePreviewError(apiError(err));
      } finally {
        if (!cancelled) setDeletePreviewLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiError, deleteTarget, workspaceId]);

  useEffect(() => {
    if (!focusStatementId) {
      setHighlightStatementId(undefined);
      return;
    }
    let cancelled = false;
    void workspaceOpenApiGET<{
      statement: {
        subject_id: string;
        surface_phrase: string;
        statement_id: string;
      };
    }>(workspaceId, `ledger/statements/${encodeURIComponent(focusStatementId)}`)
      .then((body) => {
        if (cancelled) return;
        const subjectId = body.statement.subject_id;
        setHighlightStatementId(body.statement.statement_id);
        setFactsTarget({
          entity_id: subjectId,
          id: subjectId,
          canonical_label: null,
          description: null,
          entity_kind: '',
        });
      })
      .catch(() => {
        if (!cancelled) setHighlightStatementId(undefined);
      });
    return () => {
      cancelled = true;
    };
  }, [focusStatementId, workspaceId]);

  async function confirmInvalidateEntity() {
    if (!invalidateTarget || invalidating) return;
    const entityId = ledgerEntityId(invalidateTarget);
    setInvalidating(true);
    setError(null);
    try {
      await workspaceOpenApiPOST(workspaceId, 'ledger/entities/invalidate', {
        body: { entity_ids: [entityId] },
      });
      toast.success(l.invalidate_entity_success);
      if (factsTarget && ledgerEntityId(factsTarget) === entityId) setFactsTarget(null);
      setInvalidateTarget(null);
      await fetchEntities(appliedQuery, safePage);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setInvalidating(false);
    }
  }

  async function confirmDeleteEntity() {
    if (!deleteTarget || deleting) return;
    const entityId = ledgerEntityId(deleteTarget);
    setDeleting(true);
    setError(null);
    try {
      await workspaceOpenApiDELETE(workspaceId, `ledger/entities/${encodeURIComponent(entityId)}`);
      if (factsTarget && ledgerEntityId(factsTarget) === entityId) setFactsTarget(null);
      setDeleteTarget(null);
      await fetchEntities(appliedQuery, safePage);
    } catch (err) {
      setDeletePreviewError(apiError(err));
    } finally {
      setDeleting(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    setAppliedQuery(query);
    setPage(1);
  }

  const columns = useMemo((): DataTableColumn<LedgerEntityHit>[] => {
    return [
      {
        key: 'entity',
        header: l.col_entity,
        render: (hit) => {
          const entityId = ledgerEntityId(hit);
          return (
            <EntityRefLine
              id={entityId}
              labels={{ [entityId]: hit.canonical_label, ...nodeLabels }}
            />
          );
        },
      },
      {
        key: 'kind',
        header: l.col_kind,
        width: '6rem',
        hideBelow: 'sm',
        render: (hit) =>
          hit.entity_kind ? (
            <Badge variant="secondary" className="max-w-full truncate">
              {hit.entity_kind}
            </Badge>
          ) : (
            <span className="text-muted-foreground">{emptyCell}</span>
          ),
      },
      {
        key: 'description',
        header: l.col_description,
        hideBelow: 'md',
        render: (hit) => (
          <span className="line-clamp-2 text-muted-foreground">{hit.description || emptyCell}</span>
        ),
      },
      {
        key: 'actions',
        header: l.col_actions,
        align: 'right',
        width: '5rem',
        render: (hit) => {
          const entityId = ledgerEntityId(hit);
          return (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={(event) => event.stopPropagation()}
                >
                  <PublicIcon name="dot-horizontal" size={16} />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => setFactsTarget(hit)}>
                  {l.view_facts}
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to={`${workspacePath(workspaceId, 'graph')}?focus=${encodeURIComponent(entityId)}`}>
                    {l.open_in_graph}
                  </Link>
                </DropdownMenuItem>
                {showLineage ? (
                  <DropdownMenuItem asChild>
                    <Link to={`${workspacePath(workspaceId, 'lineage')}?node=${encodeURIComponent(entityId)}`}>
                      {l.open_lineage}
                    </Link>
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to={`${workspacePath(workspaceId, 'search')}?entity=${encodeURIComponent(entityId)}`}>
                    {l.search_chunks}
                  </Link>
                </DropdownMenuItem>
                {canDeleteEntity ? (
                  <>
                    <DropdownMenuItem onClick={() => setInvalidateTarget(hit)}>
                      {l.invalidate_entity}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => setDeleteTarget(hit)}
                    >
                      {l.delete_entity}
                    </DropdownMenuItem>
                  </>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          );
        },
      },
    ];
  }, [canDeleteEntity, emptyCell, workspaceId, l, nodeLabels, showLineage]);

  return (
    <DataPanel>
      <form onSubmit={(e) => void onSubmit(e)}>
        <DataPanelToolbar
          search={
            <ToolbarSearch
              className="w-full min-w-[12rem] max-w-md sm:w-72"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={l.entity_placeholder}
            />
          }
          actions={
            <Button type="submit" size="sm" disabled={loading}>
              {loading ? <Spinner className="size-4" /> : null}
              {loading ? l.searching : l.search}
            </Button>
          }
        />
      </form>
      <DataPanelBody padded={false} className="mt-2">
        {error ? <p className="px-4 py-3 text-sm text-destructive">{error}</p> : null}
        {loading && entities.length === 0 ? (
          <div className="flex justify-center py-16">
            <Spinner className="size-6" />
          </div>
        ) : entities.length === 0 ? (
          <EmptyState
            title={l.no_entities}
            description={l.empty_browse_hint}
          />
        ) : (
          <>
            <DataTable
              columns={columns}
              data={entities}
              rowKey={(hit) => ledgerEntityId(hit)}
              onRowClick={setFactsTarget}
              className="border-0"
            />
            <DataPanelTableFooter
              countLabel={countLabel}
              page={safePage}
              totalPages={totalPages}
              onPageChange={setPage}
            />
          </>
        )}
      </DataPanelBody>

      <Dialog
        open={factsTarget !== null}
        onOpenChange={(open) => {
          if (!open) setFactsTarget(null);
        }}
      >
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{l.entity_facts_title}</DialogTitle>
            <DialogDescription>
              {factsTarget
                ? factsTarget.canonical_label || ledgerEntityId(factsTarget)
                : ''}
            </DialogDescription>
          </DialogHeader>
          {factsTarget ? (
            <EntityFactsPanel
              workspaceId={workspaceId}
              entityId={ledgerEntityId(factsTarget)}
              highlightStatementId={highlightStatementId}
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog
        open={invalidateTarget !== null}
        onOpenChange={(open) => {
          if (!open && !invalidating) setInvalidateTarget(null);
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{l.invalidate_entity_title}</DialogTitle>
            <DialogDescription>
              {fmt(l.invalidate_entity_description, {
                label:
                  invalidateTarget?.canonical_label ||
                  (invalidateTarget ? ledgerEntityId(invalidateTarget) : ''),
              })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={invalidating}
              onClick={() => setInvalidateTarget(null)}
            >
              {t.core.common.cancel}
            </Button>
            <Button type="button" disabled={invalidating} onClick={() => void confirmInvalidateEntity()}>
              {invalidating ? <Spinner className="size-4" /> : null}
              {l.invalidate_entity_confirm}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deleting) setDeleteTarget(null);
        }}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{l.delete_entity_title}</DialogTitle>
            <DialogDescription>
              {fmt(l.delete_entity_description, {
                label: deleteTarget?.canonical_label || (deleteTarget ? ledgerEntityId(deleteTarget) : ''),
              })}
            </DialogDescription>
          </DialogHeader>
          {deletePreviewLoading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              {l.delete_entity_loading}
            </div>
          ) : null}
          {deletePreviewError ? (
            <p className="text-sm text-destructive">{deletePreviewError}</p>
          ) : null}
          {deletePreview && !deletePreviewLoading ? (
            <div className="space-y-3">
              {deletePreview.statements.length === 0 ? (
                <p className="text-sm text-muted-foreground">{l.delete_entity_none}</p>
              ) : (
                <ul className="max-h-[min(50vh,18rem)] space-y-2 overflow-y-auto text-sm">
                  {deletePreview.statements.map((statement) => (
                    <li key={statement.statement_id} className="rounded-md border border-border p-3">
                      <div>{statementDeleteLine(statement)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{statement.status}</div>
                      {statement.evidence_quote ? (
                        <blockquote className="mt-2 border-l-2 pl-2 text-xs text-muted-foreground">
                          {statement.evidence_quote}
                        </blockquote>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
              {deletePreview.statements_truncated ? (
                <p className="text-xs text-muted-foreground">
                  {fmt(l.delete_entity_truncated, {
                    shown: deletePreview.statements.length,
                    total: deletePreview.statement_count,
                  })}
                </p>
              ) : null}
              {deletePreview.typed_fact_count > 0 ||
              deletePreview.derived_fact_count > 0 ||
              deletePreview.merge_count > 0 ? (
                <p className="text-sm text-muted-foreground">
                  {fmt(l.delete_entity_related, {
                    typed: deletePreview.typed_fact_count,
                    derived: deletePreview.derived_fact_count,
                    merges: deletePreview.merge_count,
                  })}
                </p>
              ) : null}
            </div>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              disabled={deleting}
              onClick={() => setDeleteTarget(null)}
            >
              {t.core.common.cancel}
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={deleting || deletePreviewLoading || deletePreview === null}
              onClick={() => void confirmDeleteEntity()}
            >
              {deleting ? <Spinner className="size-4" /> : null}
              {l.delete_entity_confirm}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DataPanel>
  );
}
