import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  DataPanel,
  DataPanelBody,
  DataPanelTableFooter,
  DataPanelToolbar,
  EmptyState,
  ToolbarSearch,
} from '@/components/app/shared/console/index.js';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { Button } from '@/components/ui/button.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Spinner } from '@/components/ui/spinner.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { formatGraphAuditAction } from '@/modules/graph/lib/graph-audit.js';
import {
  workspaceOpenApiGET,
  workspaceOpenApiPOST,
} from '@/lib/openapi/client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { fetchWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { formatNodeRef } from '@/lib/workspace/format-node-ref.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime, formatLocaleNumber, pickCountForm } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import {
  auditDetailLine,
  collectAuditLabelIds,
  collectMergeLabelIds,
  type AuditEvent,
  type EntityMergeRow,
} from '@/modules/activity-log/lib/timeline.js';
import {
  buildActivityLogRows,
  filterActivityLogRows,
  type ActivityLogKindFilter,
  type ActivityLogRow,
} from '@/modules/activity-log/lib/rows.js';
import { graphDecisionIdFromActivityRow } from '@/modules/activity-log/lib/graph-decision-id.js';
import {
  activityLogAuditSummaryLine,
  collectReviewItemIdsFromAuditEvents,
  formatAuditActorLabel,
  type WorkspaceMemberRow,
} from '@/modules/activity-log/lib/audit-display.js';
import { fetchReviewItemsById } from '@/modules/activity-log/lib/fetch-review-items.js';
import { collectReviewItemLabelIds } from '@/modules/review/lib/review-item-summary.js';
import type { ReviewItemSummaryInput } from '@/modules/review/lib/review-item-summary.js';
import {
  type DecisionRow,
  decisionListTitle,
  decisionListPreview,
} from '@/modules/decisions/lib/decision-display.js';
import {
  decisionCategoryLabel,
  decisionOutcomeLabel,
} from '@/modules/decisions/i18n/screen-copy.js';
import { GraphDecisionDetailDialog } from '@/modules/activity-log/components/graph-decision-detail-dialog.js';
import { GraphDecisionsBrowseDialog } from '@/modules/activity-log/components/graph-decisions-browse-dialog.js';
import { GraphDecisionsList } from '@/modules/activity-log/components/graph-decisions-list.js';
import {
  DECISIONS_BROWSE_PARAM,
  mergeActivityLogGraphDecisionParam,
  parseActivityLogDecisionUrlState,
} from '@/modules/review/lib/review-url-state.js';

const FETCH_LIMIT = 200;
const PAGE_SIZE = 25;

const KIND_VALUES = ['all', 'audit', 'ledger_merge', 'graph_decision'] as const;
type KindFilter = (typeof KIND_VALUES)[number];

const ACTION_PREFIX_VALUES = ['workspace.', 'workspace.graph.'] as const;
type ActionPrefix = (typeof ACTION_PREFIX_VALUES)[number];

function parsePage(raw: string | null): number {
  const n = Number.parseInt(raw ?? '1', 10);
  return Number.isFinite(n) && n >= 1 ? n : 1;
}

function parseKind(raw: string | null): KindFilter {
  if (raw === 'audit' || raw === 'ledger_merge' || raw === 'graph_decision') return raw;
  return 'all';
}

function parseActionPrefix(raw: string | null): ActionPrefix {
  if (raw === 'workspace.graph.') return raw;
  return 'workspace.';
}

export function ActivityLogPanel({ workspaceId }: { workspaceId: string }) {
  const { t, locale } = useI18n();
  const p = t.activity_log.page;
  const r = t.review.queue;
  const auditMessages = t.graph.audit;
  const emptyCell = t.core.common.emptyCell;
  const { caps } = useWorkspaceCapabilities();
  const dec = t.decisions.page;
  const canRevertMerge = Boolean(caps?.graph_write);

  const [searchParams, setSearchParams] = useSearchParams();
  const kindFilter = parseKind(searchParams.get('kind'));
  const actionPrefix = parseActionPrefix(searchParams.get('action_prefix'));
  const page = parsePage(searchParams.get('page'));
  const [search, setSearch] = useState('');

  const [events, setEvents] = useState<(AuditEvent & { actor_id?: string | null })[]>([]);
  const [merges, setMerges] = useState<EntityMergeRow[]>([]);
  const [labels, setLabels] = useState<Record<string, string | null>>({});
  const [membersByUserId, setMembersByUserId] = useState<Map<string, WorkspaceMemberRow>>(
    () => new Map(),
  );
  const [reviewItemsById, setReviewItemsById] = useState<Map<string, ReviewItemSummaryInput>>(
    () => new Map(),
  );
  const [graphDecisions, setGraphDecisions] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyMergeId, setBusyMergeId] = useState<string | null>(null);
  const [decisionDialogId, setDecisionDialogId] = useState<string | null>(null);
  const [decisionDialogOpen, setDecisionDialogOpen] = useState(false);
  const [browseDialogOpen, setBrowseDialogOpen] = useState(false);

  const urlDecisionState = parseActivityLogDecisionUrlState(searchParams.toString());

  const openGraphDecisionDetail = useCallback(
    (id: string, syncUrl = true) => {
      const trimmed = id.trim();
      if (!trimmed) return;
      setDecisionDialogId(trimmed);
      setDecisionDialogOpen(true);
      if (syncUrl) {
        const next = mergeActivityLogGraphDecisionParam(searchParams.toString(), trimmed);
        setSearchParams(next, { replace: true });
      }
    },
    [searchParams, setSearchParams],
  );

  const closeGraphDecisionDetail = useCallback(
    (open: boolean) => {
      setDecisionDialogOpen(open);
      if (!open) {
        setDecisionDialogId(null);
        const next = mergeActivityLogGraphDecisionParam(searchParams.toString(), null);
        setSearchParams(next, { replace: true });
      }
    },
    [searchParams, setSearchParams],
  );

  const setBrowseOpen = useCallback(
    (open: boolean) => {
      setBrowseDialogOpen(open);
      const next = new URLSearchParams(searchParams);
      if (open) next.set(DECISIONS_BROWSE_PARAM, '1');
      else next.delete(DECISIONS_BROWSE_PARAM);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    const id = urlDecisionState.graphDecisionId;
    if (!id) return;
    setDecisionDialogId(id);
    setDecisionDialogOpen(true);
  }, [urlDecisionState.graphDecisionId]);

  useEffect(() => {
    if (urlDecisionState.openBrowse) setBrowseDialogOpen(true);
  }, [urlDecisionState.openBrowse]);

  const load = useCallback(async (mode: 'initial' | 'refresh' = 'initial') => {
    if (mode === 'initial') setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const needAudit = kindFilter === 'all' || kindFilter === 'audit';
      const needMerges = kindFilter === 'all' || kindFilter === 'ledger_merge';

      const auditPromise = needAudit
        ? workspaceOpenApiGET<{ events?: (AuditEvent & { actor_id?: string | null })[] }>(
            workspaceId,
            'audit/graph-mutations',
            {
              params: {
                query: { action_prefix: actionPrefix, limit: FETCH_LIMIT },
              },
            },
          )
        : Promise.resolve(null);
      const mergesPromise = needMerges
        ? workspaceOpenApiGET<{ merges?: EntityMergeRow[] }>(workspaceId, 'ledger/entity-merges', {
            params: {
              query: { active_only: false, limit: FETCH_LIMIT },
            },
          })
        : Promise.resolve(null);

      const decisionsPromise =
        kindFilter === 'all' && caps?.graph_runtime
          ? workspaceOpenApiGET<DecisionRow[]>(workspaceId, 'decisions', {
              params: { query: { limit: 200 } },
            }).catch(() => [] as DecisionRow[])
          : Promise.resolve([] as DecisionRow[]);

      const [auditData, mergeData, decisionsData] = await Promise.all([
        auditPromise,
        mergesPromise,
        decisionsPromise,
      ]);
      setGraphDecisions(Array.isArray(decisionsData) ? decisionsData : []);

      let loadedEvents: (AuditEvent & { actor_id?: string | null })[] = [];
      if (auditData) {
        loadedEvents = auditData.events ?? [];
        setEvents(loadedEvents);
      } else {
        setEvents([]);
      }

      let loadedMerges: EntityMergeRow[] = [];
      if (mergeData) {
        loadedMerges = mergeData.merges ?? [];
        setMerges(loadedMerges);
      } else {
        setMerges([]);
      }

      let reviewMapForLabels: Map<string, ReviewItemSummaryInput> = new Map();
      if (loadedEvents.length > 0) {
        const reviewIds = collectReviewItemIdsFromAuditEvents(loadedEvents);
        const [membersBody, reviewMap] = await Promise.all([
          workspaceOpenApiGET<{ members?: WorkspaceMemberRow[] }>(workspaceId, 'members').catch(
            () => ({ members: [] as WorkspaceMemberRow[] }),
          ),
          fetchReviewItemsById(workspaceId, reviewIds),
        ]);
        setMembersByUserId(new Map((membersBody.members ?? []).map((m) => [m.user_id, m])));
        setReviewItemsById(reviewMap);
        reviewMapForLabels = reviewMap;
      } else {
        setMembersByUserId(new Map());
        setReviewItemsById(new Map());
      }

      const labelIds = [
        ...collectAuditLabelIds(loadedEvents),
        ...collectMergeLabelIds(loadedMerges),
        ...collectReviewItemLabelIds(reviewMapForLabels.values()),
      ];
      if (labelIds.length > 0) {
        void fetchWorkspaceNodeLabels(workspaceId, labelIds)
          .then((next) => setLabels(next))
          .catch(() => {});
      } else {
        setLabels({});
      }
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
      setEvents([]);
      setMerges([]);
      setGraphDecisions([]);
    } finally {
      if (mode === 'initial') setLoading(false);
      else setRefreshing(false);
    }
  }, [actionPrefix, caps?.graph_runtime, kindFilter, locale, workspaceId]);

  useEffect(() => {
    void load('initial');
  }, [load]);

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(searchParams);
    if (!value) next.delete(key);
    else next.set(key, value);
    if (key !== 'page') next.delete('page');
    setSearchParams(next, { replace: true });
  }

  const allRows = useMemo(
    () =>
      buildActivityLogRows(events, merges, kindFilter as ActivityLogKindFilter, graphDecisions),
    [events, graphDecisions, kindFilter, merges],
  );

  const rowSearchText = useCallback(
    (row: ActivityLogRow): string => {
      if (row.kind === 'ledger_merge') {
        const m = row.merge;
        return [
          r.ledger_merge_label,
          formatNodeRef(m.source_entity_id, labels),
          formatNodeRef(m.target_entity_id, labels),
          m.why ?? '',
        ].join(' ');
      }
      if (row.kind === 'graph_decision') {
        const d = row.decision;
        return [
          p.kind_graph_decision,
          decisionListTitle(d, dec),
          decisionListPreview(d),
          d.decision_id,
          d.category,
          d.outcome,
        ]
          .filter(Boolean)
          .join(' ');
      }
      const event = row.event;
      const summaryLine = activityLogAuditSummaryLine(event, {
        locale: locale as Locale,
        reviewItemsById,
        reviewCopy: r,
        activityLogCopy: p,
        labels,
        emptyCell,
        auditDetailLine: auditDetailLine(locale, event, r, auditMessages, labels),
      });
      return [
        formatGraphAuditAction(event.action, locale as Locale),
        event.action,
        summaryLine,
        formatAuditActorLabel(event.actor_id, membersByUserId, emptyCell, p.actor_system),
      ].join(' ');
    },
    [auditMessages, dec, emptyCell, labels, locale, membersByUserId, p, r, reviewItemsById],
  );

  const filteredRows = useMemo(
    () => filterActivityLogRows(allRows, search, rowSearchText),
    [allRows, rowSearchText, search],
  );

  const showEmpty = !loading && filteredRows.length === 0;

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);

  useEffect(() => {
    if (page <= totalPages) return;
    const next = new URLSearchParams(searchParams);
    if (totalPages <= 1) next.delete('page');
    else next.set('page', String(totalPages));
    setSearchParams(next, { replace: true });
  }, [page, searchParams, setSearchParams, totalPages]);

  const pageRows = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return filteredRows.slice(start, start + PAGE_SIZE);
  }, [filteredRows, safePage]);

  async function revertLedgerMerge(mergeId: string) {
    if (!canRevertMerge) return;
    setBusyMergeId(mergeId);
    try {
      await workspaceOpenApiPOST(
        workspaceId,
        `ledger/entity-merges/${encodeURIComponent(mergeId)}/revert`,
      );
      void load('refresh');
    } catch (err) {
      setError(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setBusyMergeId(null);
    }
  }

  const columns = useMemo<DataTableColumn<ActivityLogRow>[]>(
    () => [
      {
        key: 'time',
        header: p.col_time,
        render: (row) =>
          row.at ? formatLocaleDateTime(locale as Locale, row.at) : emptyCell,
      },
      {
        key: 'kind',
        header: p.col_kind,
        hideBelow: 'sm',
        render: (row) => {
          if (row.kind === 'graph_decision' || graphDecisionIdFromActivityRow(row)) {
            return p.kind_graph_decision_row;
          }
          return row.kind === 'ledger_merge' ? p.kind_ledger_merge : p.kind_audit;
        },
      },
      {
        key: 'action',
        header: p.col_action,
        render: (row) => {
          if (row.kind === 'graph_decision') {
            const d = row.decision;
            const parts = [
              d.category ? decisionCategoryLabel(dec, d.category) : '',
              d.outcome ? decisionOutcomeLabel(dec, d.outcome) : '',
            ].filter(Boolean);
            return (
              <span className="text-xs font-medium text-foreground">
                {parts.join(' · ') || p.kind_graph_decision_row}
              </span>
            );
          }
          if (row.kind === 'ledger_merge') {
            const m = row.merge;
            return (
              <span className="text-xs font-medium">
                {r.ledger_merge_label}
                {m.reverted_at ? r.ledger_merge_reverted : ''}
              </span>
            );
          }
          const label = formatGraphAuditAction(row.event.action, locale as Locale);
          return (
            <span className="text-xs font-medium text-foreground">
              {label || row.event.action || emptyCell}
            </span>
          );
        },
      },
      {
        key: 'summary',
        header: p.col_summary,
        hideBelow: 'md',
        render: (row) => {
          if (row.kind === 'graph_decision') {
            const d = row.decision;
            const title = decisionListTitle(d, dec);
            const preview = decisionListPreview(d);
            return (
              <span className="line-clamp-2 text-xs text-muted-foreground">
                {preview ? `${title} · ${preview}` : title}
              </span>
            );
          }
          if (row.kind === 'ledger_merge') {
            const m = row.merge;
            return (
              <span className="line-clamp-2 text-xs text-muted-foreground">
                {formatNodeRef(m.source_entity_id, labels)} → {formatNodeRef(m.target_entity_id, labels)}
                {m.why ? ` · ${m.why}` : ''}
              </span>
            );
          }
          const event = row.event;
          const line = activityLogAuditSummaryLine(event, {
            locale: locale as Locale,
            reviewItemsById,
            reviewCopy: r,
            activityLogCopy: p,
            labels,
            emptyCell,
            auditDetailLine: auditDetailLine(locale, event, r, auditMessages, labels),
          });
          return <span className="line-clamp-2 text-xs text-muted-foreground">{line}</span>;
        },
      },
      {
        key: 'actor',
        header: p.col_actor,
        hideBelow: 'md',
        render: (row) =>
          row.kind === 'audit'
            ? formatAuditActorLabel(row.event.actor_id, membersByUserId, emptyCell, p.actor_system)
            : emptyCell,
      },
      {
        key: 'actions',
        header: p.col_actions,
        render: (row) => {
          if (row.kind !== 'ledger_merge' || row.merge.reverted_at || !canRevertMerge) {
            return emptyCell;
          }
          return (
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8"
              disabled={busyMergeId === row.merge.id}
              onClick={(event) => {
                event.stopPropagation();
                void revertLedgerMerge(row.merge.id);
              }}
            >
              {busyMergeId === row.merge.id ? (
                <Spinner className="size-3" />
              ) : (
                r.revert_merge
              )}
            </Button>
          );
        },
      },
    ],
    [
      auditMessages,
      busyMergeId,
      canRevertMerge,
      emptyCell,
      labels,
      locale,
      membersByUserId,
      p,
      r,
      reviewItemsById,
      workspaceId,
    ],
  );

  const countLabel = fmt(
    pickCountForm(locale, filteredRows.length, p.count_one, p.count_many),
    { count: formatLocaleNumber(locale, filteredRows.length) },
  );

  return (
    <DataPanel data-testid="activity-log-panel">
      <DataPanelToolbar
        className="flex-nowrap"
        search={
          <ToolbarSearch
            className="min-w-0 w-full max-w-md flex-1 sm:w-72 sm:flex-none"
            placeholder={p.search_placeholder}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            disabled={loading && allRows.length === 0}
          />
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Select
              value={kindFilter}
              onValueChange={(value) => setParam('kind', value === 'all' ? null : value)}
            >
              <SelectTrigger className="w-[9.5rem]" size="sm">
                <SelectValue placeholder={p.kind_placeholder} />
              </SelectTrigger>
              <SelectContent>
                {KIND_VALUES.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value === 'all'
                      ? p.kind_all
                      : value === 'audit'
                        ? p.kind_audit
                        : value === 'ledger_merge'
                          ? p.kind_ledger_merge
                          : p.kind_graph_decision}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={actionPrefix}
              onValueChange={(value) => setParam('action_prefix', value)}
              disabled={kindFilter === 'ledger_merge'}
            >
              <SelectTrigger className="w-[10.5rem]" size="sm">
                <SelectValue placeholder={p.action_prefix_placeholder} />
              </SelectTrigger>
              <SelectContent>
                {ACTION_PREFIX_VALUES.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value === 'workspace.' ? p.action_prefix_workspace : p.action_prefix_graph}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              type="button"
              variant="outline"
              size="sm"
              data-testid="activity-log-browse-decisions"
              onClick={() => setBrowseOpen(true)}
            >
              {p.browse_decisions_button}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={loading || refreshing}
              onClick={() => void load('refresh')}
            >
              <PublicIcon
                name="arrow-refresh-01"
                className={`mr-1.5 size-3.5 ${refreshing ? 'animate-spin' : ''}`}
              />
              {p.refresh}
            </Button>
          </div>
        }
      />
      <DataPanelBody padded={false} className="mt-2">
        {kindFilter === 'graph_decision' ? (
          <GraphDecisionsList
            workspaceId={workspaceId}
            enabled
            initialFilter={urlDecisionState.decisionsQ ?? search}
            onSelectDecision={(id) => openGraphDecisionDetail(id)}
            className="max-h-[min(70vh,40rem)]"
          />
        ) : (
          <>
        {error ? (
          <p className="border-b border-border px-4 py-3 text-sm text-destructive">{error}</p>
        ) : null}
        {loading && allRows.length === 0 ? (
          <div className="flex justify-center py-16">
            <Spinner className="size-6" />
          </div>
        ) : showEmpty ? (
          <EmptyState title={p.empty_title} description={p.empty_description} />
        ) : (
          <>
            <DataTable
              columns={columns}
              data={pageRows}
              rowKey={(row) => row.rowKey}
              className="border-0"
              onRowClick={(row) => {
                const id = graphDecisionIdFromActivityRow(row);
                if (!id) return;
                openGraphDecisionDetail(id);
              }}
              rowClassName={(row) =>
                graphDecisionIdFromActivityRow(row) ? 'hover:bg-muted/50' : undefined
              }
            />
            <DataPanelTableFooter
              countLabel={countLabel}
              page={safePage}
              totalPages={totalPages}
              onPageChange={(nextPage) =>
                setParam('page', nextPage <= 1 ? null : String(nextPage))
              }
            />
          </>
        )}
          </>
        )}
      </DataPanelBody>
      <GraphDecisionDetailDialog
        workspaceId={workspaceId}
        decisionId={decisionDialogId}
        open={decisionDialogOpen}
        onOpenChange={closeGraphDecisionDetail}
      />
      <GraphDecisionsBrowseDialog
        workspaceId={workspaceId}
        open={browseDialogOpen}
        onOpenChange={setBrowseOpen}
        initialFilter={urlDecisionState.decisionsQ ?? ''}
        onSelectDecision={(id) => openGraphDecisionDetail(id)}
      />
    </DataPanel>
  );
}
