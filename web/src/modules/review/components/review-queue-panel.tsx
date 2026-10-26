import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { EntityMergePropertyDiff } from '@/modules/entity-resolution/components/entity-merge-property-diff.js';
import { ReviewDecisionNarrative } from './review-decision-narrative.js';
import {
  GovernanceScanDialog,
  type GovernanceScanOptions,
} from './governance-scan-dialog.js';
import {
  workspaceOpenApiGET,
  workspaceOpenApiPOST,
} from '@/lib/openapi/client.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import {
  formatUserFacingApiError,
  isGovernanceGateErrorCode,
  readApiErrorCode,
} from '@/lib/errors/api-error-message.js';
import { formatNodeRef, formatNodeRefDetail } from '@/lib/workspace/format-node-ref.js';
import {
  type AuditEvent,
  collectAuditLabelIds,
  decisionIdsForReviewItem,
} from '@/modules/activity-log/lib/timeline.js';
import { fetchWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { workspaceAlertsPath, reviewAlertEpisodeKey } from '@/modules/alerts/lib/alerts-url.js';
import { workspaceOntologyProposalPath, workspaceOntologyVersionsPath, workspacePath } from '@/lib/nav/nav-config.js';
import { workspaceOntologyHubPath } from '@/modules/analyze/lib/hub-route.js';
import {
  activityLogBrowseDecisionsPath,
  decisionIdFromApproveResponse,
  reviewDecisionPath,
  reviewItemPath,
} from '@/modules/review/lib/review-url-state.js';
import {
  reviewItemQualityHref,
  reviewItemQualityLinkLabelKey,
} from '@/modules/review/lib/review-quality-link.js';
import { reviewItemSummaryLine } from '@/modules/review/lib/review-item-summary.js';
import { Button } from '@/components/ui/button.js';
import { cn } from '@/lib/utils.js';
import { toast } from 'sonner';

const REVIEW_PAGE_SIZE = 50;

type ReviewItem = {
  id: string;
  kind: string;
  status: string;
  payload: {
    primary_id?: string;
    duplicate_ids?: string[];
    filename?: string;
    byte_size?: number;
    mapping_id?: string;
    signature?: string;
    target_uri?: string | null;
    target_kind?: string;
    direction?: string;
    content?: string;
    statement_id?: string;
    surface_phrase?: string;
    predicate_iri?: string | null;
    mapping_status?: string;
    conflict_type?: string;
    schema_version?: number;
    confidence?: number;
    confidence_min?: number;
    subject_id?: string;
    objects?: Array<{
      statement_id?: string;
      object_entity_id?: string | null;
      object_value?: string | null;
      status?: string;
      proposed_by?: string | null;
      quote?: string | null;
    }>;
    outbox_id?: string;
    entity_id?: string;
    entity_ids?: string[];
    suggested_primary_id?: string;
    canonical_label?: string;
    provider?: string;
    external_table?: string;
    external_pk?: string;
    changes?: Record<string, { old?: unknown; new?: unknown }>;
  };
  created_at: string;
};

function collectReviewItemLabelIds(items: ReviewItem[]): string[] {
  const ids: string[] = [];
  for (const item of items) {
    if (item.kind === 'entity_merge' && item.payload) {
      if (item.payload.primary_id) ids.push(item.payload.primary_id);
      ids.push(...(item.payload.duplicate_ids ?? []));
    }
    if (item.kind === 'shacl_violation') {
      if (item.payload.subject_id) ids.push(item.payload.subject_id);
      for (const obj of item.payload.objects ?? []) {
        if (obj.object_entity_id) ids.push(obj.object_entity_id);
      }
    }
    if (item.kind === 'entity_cluster') {
      ids.push(...(item.payload.entity_ids ?? []));
      if (item.payload.suggested_primary_id) ids.push(item.payload.suggested_primary_id);
    }
  }
  return ids;
}

export function ReviewQueuePanel({
  workspaceId,
  focusItemId,
}: {
  workspaceId: string;
  focusItemId?: string;
}) {
  const { t, locale } = useI18n();
  const emptyCell = t.core.common.emptyCell;
  const r = t.review.queue;
  const apiError = useCallback(
    (err: unknown) => formatUserFacingApiError(err, locale as Locale),
    [locale],
  );
  const { caps } = useWorkspaceCapabilities();
  const queryClient = useQueryClient();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [queueTotal, setQueueTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const loadMoreSentinelRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [gateErrorCode, setGateErrorCode] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [labels, setLabels] = useState<Record<string, string | null>>({});
  const [diffExpandedId, setDiffExpandedId] = useState<string | null>(null);
  const [highlightItemId, setHighlightItemId] = useState<string | null>(null);
  const [approvedDecisionId, setApprovedDecisionId] = useState<string | null>(null);
  const [focusedResolvedItem, setFocusedResolvedItem] = useState<ReviewItem | null>(null);
  const [governorBusy, setGovernorBusy] = useState(false);
  const [governorDialogOpen, setGovernorDialogOpen] = useState(false);
  const [clusterPrimary, setClusterPrimary] = useState<Record<string, string>>({});
  const canRunGovernor = Boolean(caps?.graph_write);

  useEffect(() => {
    setClusterPrimary((prev) => {
      const next = { ...prev };
      for (const item of items) {
        if (item.kind !== 'entity_cluster') continue;
        if (next[item.id]) continue;
        const suggested =
          item.payload.suggested_primary_id ?? item.payload.entity_ids?.[0];
        if (suggested) next[item.id] = suggested;
      }
      return next;
    });
  }, [items]);

  const mergeQueueLabels = useCallback(
    (queueItems: ReviewItem[]) => {
      const labelIds = collectReviewItemLabelIds(queueItems);
      if (labelIds.length === 0) return;
      void fetchWorkspaceNodeLabels(workspaceId, labelIds)
        .then((next) => setLabels((prev) => ({ ...prev, ...next })))
        .catch(() => {});
    },
    [workspaceId],
  );

  const load = useCallback(async (): Promise<number> => {
    setLoading(true);
    setLoadingMore(false);
    setError(null);
    try {
      const [queueData, auditData] = await Promise.all([
        workspaceOpenApiGET<{
          items?: ReviewItem[];
          total?: number;
          has_more?: boolean;
        }>(workspaceId, 'review/items', {
          params: {
            query: { limit: REVIEW_PAGE_SIZE, offset: 0, status: 'open' },
          },
        }),
        workspaceOpenApiGET<{ events?: AuditEvent[] }>(workspaceId, 'audit/graph-mutations', {
          params: {
            query: { action_prefix: 'workspace.', limit: 50 },
          },
        }).catch(() => ({ events: [] as AuditEvent[] })),
      ]);
      const pageItems = queueData.items ?? [];
      const total = queueData.total ?? pageItems.length;
      setItems(pageItems);
      setQueueTotal(total);
      setHasMore(Boolean(queueData.has_more));

      const loadedEvents = auditData.events ?? [];
      setEvents(loadedEvents);

      const labelIds: string[] = [
        ...collectReviewItemLabelIds(pageItems),
        ...collectAuditLabelIds(loadedEvents),
      ];
      void fetchWorkspaceNodeLabels(workspaceId, labelIds)
        .then((next) => setLabels((prev) => ({ ...prev, ...next })))
        .catch(() => {});
      return total;
    } catch (err) {
      setError(apiError(err));
      setItems([]);
      setQueueTotal(0);
      setHasMore(false);
      setEvents([]);
      return 0;
    } finally {
      setLoading(false);
    }
  }, [apiError, workspaceId]);

  const loadMore = useCallback(async () => {
    if (loading || loadingMore || !hasMore) return;
    setLoadingMore(true);
    setError(null);
    const offset = items.length;
    try {
      const queueData = await workspaceOpenApiGET<{
        items?: ReviewItem[];
        total?: number;
        has_more?: boolean;
      }>(workspaceId, 'review/items', {
        params: {
          query: { limit: REVIEW_PAGE_SIZE, offset, status: 'open' },
        },
      });
      const pageItems = queueData.items ?? [];
      const total = queueData.total ?? queueTotal;
      setItems((prev) => [...prev, ...pageItems]);
      setQueueTotal(total);
      setHasMore(Boolean(queueData.has_more));
      mergeQueueLabels(pageItems);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoadingMore(false);
    }
  }, [apiError, hasMore, items.length, loading, loadingMore, mergeQueueLabels, queueTotal, workspaceId]);

  useEffect(() => {
    const root = scrollRef.current;
    const sentinel = loadMoreSentinelRef.current;
    if (!root || !sentinel || !hasMore || loading || loadingMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void loadMore();
      },
      { root, rootMargin: '160px', threshold: 0 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loadMore, loading, loadingMore, items.length]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!focusItemId || loading) {
      setFocusedResolvedItem(null);
      return;
    }
    if (items.some((row) => row.id === focusItemId)) {
      setFocusedResolvedItem(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const data = await workspaceOpenApiGET<{ item?: ReviewItem }>(
          workspaceId,
          `review/items/${encodeURIComponent(focusItemId)}`,
        );
        const item = data.item;
        if (!cancelled && item?.id) {
          setFocusedResolvedItem(item);
        }
      } catch {
        if (!cancelled) setFocusedResolvedItem(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [focusItemId, items, workspaceId, loading]);

  useEffect(() => {
    if (!focusItemId || loading) return;
    const item = items.find((row) => row.id === focusItemId);
    if (!item) return;
    if (item.kind === 'entity_merge') {
      setDiffExpandedId(focusItemId);
    }
    setHighlightItemId(focusItemId);
    const timer = window.setTimeout(() => {
      document.getElementById(`review-item-${focusItemId}`)?.scrollIntoView({
        block: 'nearest',
        behavior: 'smooth',
      });
    }, 0);
    if (!focusItemId) {
      const clearHighlight = window.setTimeout(() => setHighlightItemId(null), 4000);
      return () => {
        window.clearTimeout(timer);
        window.clearTimeout(clearHighlight);
      };
    }
    return () => window.clearTimeout(timer);
  }, [focusItemId, items, loading]);

  async function runGovernorPass(options: GovernanceScanOptions) {
    setGovernorBusy(true);
    setError(null);
    try {
      const body = await workspaceOpenApiPOST<{
        shacl_scan?: {
          created?: number;
          skipped?: number;
          facts_materialized?: number;
        };
        low_confidence?: { created?: number; skipped?: number };
        entity_clusters?: { created?: number; skipped?: number };
        unmapped_entity_types?: { created?: number; skipped?: number };
        graph_dedup_clusters?: { created?: number; skipped?: number; unavailable?: boolean };
      }>(workspaceId, 'governance/governor/run', {
        body: {
          confidence_min: options.confidence_min,
          dedup_threshold: options.dedup_threshold,
          include_shacl: options.include_shacl,
          include_low_confidence: options.include_low_confidence,
          include_entity_label_clusters: options.include_entity_label_clusters,
          include_unmapped_entity_types: options.include_unmapped_entity_types,
          include_graph_dedup: options.include_graph_dedup,
        },
      });
      if (options.include_graph_dedup && body.graph_dedup_clusters?.unavailable) {
        toast.warning(t.review.governance_scan.graph_dedup_unavailable);
      }
      const shaclCreated = body.shacl_scan?.created ?? 0;
      const shaclSkipped = body.shacl_scan?.skipped ?? 0;
      const lowCreated = body.low_confidence?.created ?? 0;
      const lowSkipped = body.low_confidence?.skipped ?? 0;
      const clusterCreated = body.entity_clusters?.created ?? 0;
      const clusterSkipped = body.entity_clusters?.skipped ?? 0;
      const unmappedCreated = body.unmapped_entity_types?.created ?? 0;
      const unmappedSkipped = body.unmapped_entity_types?.skipped ?? 0;
      const graphDedupCreated = body.graph_dedup_clusters?.created ?? 0;
      const graphDedupSkipped = body.graph_dedup_clusters?.skipped ?? 0;
      const createdSum =
        (options.include_shacl ? shaclCreated : 0) +
        (options.include_low_confidence ? lowCreated : 0) +
        (options.include_entity_label_clusters ? clusterCreated : 0) +
        (options.include_unmapped_entity_types ? unmappedCreated : 0) +
        (options.include_graph_dedup ? graphDedupCreated : 0);
      const skippedSum =
        (options.include_shacl ? shaclSkipped : 0) +
        (options.include_low_confidence ? lowSkipped : 0) +
        (options.include_entity_label_clusters ? clusterSkipped : 0) +
        (options.include_unmapped_entity_types ? unmappedSkipped : 0) +
        (options.include_graph_dedup ? graphDedupSkipped : 0);
      setGovernorDialogOpen(false);
      const openCount = await load();
      toast.success(r.run_governor_success_title, {
        description:
          fmt(r.run_governor_success, {
            shaclCreated: formatLocaleNumber(locale as Locale, shaclCreated),
            shaclSkipped: formatLocaleNumber(locale as Locale, shaclSkipped),
            factsMaterialized: formatLocaleNumber(
              locale as Locale,
              body.shacl_scan?.facts_materialized ?? 0,
            ),
            lowCreated: formatLocaleNumber(locale as Locale, lowCreated),
            lowSkipped: formatLocaleNumber(locale as Locale, lowSkipped),
            clusterCreated: formatLocaleNumber(locale as Locale, clusterCreated),
            clusterSkipped: formatLocaleNumber(locale as Locale, clusterSkipped),
            unmappedCreated: formatLocaleNumber(locale as Locale, unmappedCreated),
            unmappedSkipped: formatLocaleNumber(locale as Locale, unmappedSkipped),
            graphDedupCreated: formatLocaleNumber(locale as Locale, graphDedupCreated),
            graphDedupSkipped: formatLocaleNumber(locale as Locale, graphDedupSkipped),
          }) +
          (createdSum === 0 && skippedSum === 0
            ? `\n${fmt(r.run_governor_no_delta_hint, {
                openCount: formatLocaleNumber(locale as Locale, openCount),
              })}`
            : ''),
      });
    } catch (err) {
      setError(apiError(err));
      toast.error(apiError(err));
    } finally {
      setGovernorBusy(false);
    }
  }

  async function resolve(itemId: string, action: 'approve' | 'reject') {
    setBusyId(itemId);
    setError(null);
    setGateErrorCode(null);
    const item = items.find((row) => row.id === itemId);
    const payload: { rationale?: string; primary_id?: string } = {};
    if (
      action === 'approve' &&
      item?.kind === 'entity_cluster' &&
      clusterPrimary[itemId]
    ) {
      payload.primary_id = clusterPrimary[itemId];
    }
    try {
      const body = await workspaceOpenApiPOST<unknown>(
        workspaceId,
        `review/items/${encodeURIComponent(itemId)}/${action}`,
        { body: payload },
      );
      setItems((prev) => prev.filter((row) => row.id !== itemId));
      setQueueTotal((prev) => Math.max(0, prev - 1));
      if (action === 'approve') {
        const decisionId = decisionIdFromApproveResponse(body);
        setApprovedDecisionId(decisionId);
        void queryClient.invalidateQueries({ queryKey: ['graph', 'full-load', workspaceId] });
      }
      void load();
    } catch (err) {
      setGateErrorCode(readApiErrorCode(err) ?? null);
      setError(apiError(err));
    } finally {
      setBusyId(null);
    }
  }

  const narrativeDecisionId =
    approvedDecisionId ??
    (focusItemId ? decisionIdsForReviewItem(events, focusItemId).at(-1) : undefined);
  function renderDecisionLinks(decisionIds: string[], testIdPrefix: string) {
    if (decisionIds.length === 0) return null;
    return (
      <div className="mt-2 flex flex-col gap-1">
        <span className="text-[10px] text-muted-foreground">{r.related_decisions}</span>
        <div className="flex flex-wrap gap-x-2 gap-y-0.5">
          {decisionIds.map((decisionId) => (
            <Link
              key={decisionId}
              to={reviewDecisionPath(workspaceId, decisionId)}
              className="text-[11px] text-foreground underline-offset-2 hover:underline"
              data-testid={`${testIdPrefix}-${decisionId}`}
            >
              {r.open_decision}
            </Link>
          ))}
        </div>
      </div>
    );
  }

  function renderNodeRef(id: string) {
    const { title, subtitle } = formatNodeRefDetail(id, labels);
    return (
      <span className="inline-block">
        <span>{title}</span>
        {subtitle ? (
          <span className="mt-0.5 block font-mono text-[10px] font-normal text-muted-foreground">{subtitle}</span>
        ) : null}
      </span>
    );
  }

  /** Human-readable entity/graph name for review decisions (no raw UUID when a label exists). */
  function renderReadableEntity(id: string) {
    const trimmed = id.trim();
    if (!trimmed) {
      return emptyCell;
    }
    const label = labels[trimmed]?.trim();
    if (label) {
      return <span className="font-medium text-foreground">{label}</span>;
    }
    const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(trimmed);
    if (!isUuid) {
      return <span className="font-medium text-foreground">{trimmed}</span>;
    }
    return <span className="text-muted-foreground">{r.unresolved_entity}</span>;
  }

  function kindLabel(kind: string) {
    if (kind === 'graph_import') return r.kind_import;
    if (kind === 'ontology_mapping') return r.kind_mapping;
    if (kind === 'statement_remember') return r.kind_remember;
    if (kind === 'shacl_violation') return r.kind_shacl;
    if (kind === 'low_confidence') return r.kind_low_confidence;
    if (kind === 'entity_cluster') return r.kind_entity_cluster;
    if (kind === 'unmapped_entity_type') return r.kind_unmapped_entity_type;
    if (kind === 'vocabulary_alignment_change') return r.kind_vocabulary_alignment_change;
    if (kind === 'connector_writeback') return r.kind_writeback;
    if (kind === 'entity_merge') return r.kind_merge;
    return kind;
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
          <PublicIcon name="check-square-contained" size={13} className="shrink-0 text-muted-foreground" />
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{r.queue_title}</span>
          {!loading ? (
            <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
              {fmt(r.queue_total, {
                total: formatLocaleNumber(locale as Locale, queueTotal),
              })}
            </span>
          ) : null}
          {canRunGovernor ? (
            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              <Button
                type="button"
                variant="default"
                size="sm"
                className="h-8 gap-1.5 px-3 text-xs font-medium shadow-none"
                disabled={governorBusy || loading}
                data-testid="review-run-governor"
                onClick={() => setGovernorDialogOpen(true)}
              >
                {governorBusy ? (
                  <PublicIcon name="loader-01" size={14} className="animate-spin" />
                ) : (
                  <PublicIcon name="shield-check" size={14} className="opacity-90" />
                )}
                {governorBusy ? r.run_governor_busy : r.run_governor}
              </Button>
            </div>
          ) : null}
        </div>
        {canRunGovernor ? (
          <GovernanceScanDialog
            workspaceId={workspaceId}
            open={governorDialogOpen}
            onOpenChange={setGovernorDialogOpen}
            busy={governorBusy}
            onRun={runGovernorPass}
          />
        ) : null}
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto">
          {approvedDecisionId ? (
            <div className="border-b border-border px-4 py-3">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-foreground">
                <span>{r.approve_decision_recorded}</span>
                <Link
                  to={reviewDecisionPath(workspaceId, approvedDecisionId)}
                  className="font-medium underline-offset-2 hover:underline"
                  data-testid="review-approve-decision-link"
                >
                  {r.open_decision}
                </Link>
              </div>
              <ReviewDecisionNarrative
                workspaceId={workspaceId}
                decisionId={approvedDecisionId}
                variant="embedded"
              />
            </div>
          ) : null}
          {focusedResolvedItem ? (
            <div
              className="border-b border-border px-4 py-3 text-sm"
              data-testid="review-resolved-item-banner"
            >
              <p className="text-[11px] text-muted-foreground">
                {fmt(r.resolved_review_item_hint, { status: focusedResolvedItem.status })}
              </p>
              {renderDecisionLinks(
                decisionIdsForReviewItem(events, focusedResolvedItem.id),
                'review-resolved-decision',
              )}
              {narrativeDecisionId ? (
                <ReviewDecisionNarrative
                  workspaceId={workspaceId}
                  decisionId={narrativeDecisionId}
                  variant="embedded"
                />
              ) : null}
            </div>
          ) : null}
          {loading ? (
            <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
              <PublicIcon name="loader-01" size={16} className="animate-spin" />
              {t.core.common.loading}
            </div>
          ) : error ? (
            <div className="space-y-2 px-4 py-3">
              <p className="text-sm text-destructive">{error}</p>
              {gateErrorCode && isGovernanceGateErrorCode(gateErrorCode) ? (
                <p className="text-xs text-muted-foreground">
                  {r.governance_gate_alerts_hint}{' '}
                  <Link
                    to={workspaceAlertsPath(workspaceId, {
                      episodeKey: focusItemId
                        ? reviewAlertEpisodeKey(focusItemId)
                        : undefined,
                    })}
                    className="font-medium text-primary hover:underline"
                    data-testid="review-governance-alerts-link"
                  >
                    {r.view_governance_alerts}
                  </Link>
                </p>
              ) : null}
            </div>
          ) : items.length === 0 ? (
            <div className="flex h-full min-h-32 flex-col items-center justify-center px-6 text-center">
              <PublicIcon name="check-square-contained" size={18} className="mb-2 text-muted-foreground" />
              <p className="text-sm font-medium text-foreground">{r.empty_queue}</p>
              <p className="mt-1 max-w-sm text-[11px] leading-snug text-muted-foreground">
                {r.empty_queue_prefix}
                <Link to={workspaceOntologyVersionsPath(workspaceId)} className="text-foreground underline-offset-2 hover:underline">
                  {r.empty_queue_link}
                </Link>
                {r.empty_queue_suffix}
              </p>
            </div>
          ) : (
            <ul>
              {items.map((item) => {
                const isImport = item.kind === 'graph_import';
                const isMapping = item.kind === 'ontology_mapping';
                const isRemember = item.kind === 'statement_remember';
                const isShacl = item.kind === 'shacl_violation';
                const isLowConfidence = item.kind === 'low_confidence';
                const isUnmappedEntityType = item.kind === 'unmapped_entity_type';
                const isVocabularyAlignment = item.kind === 'vocabulary_alignment_change';
                const isEntityCluster = item.kind === 'entity_cluster';
                const isWriteback = item.kind === 'connector_writeback';
                const isEntityMerge = item.kind === 'entity_merge';
                const primaryId = item.payload.primary_id ?? emptyCell;
                const duplicateIds = item.payload.duplicate_ids ?? [];
                const firstDuplicate = duplicateIds[0];
                const showDiff = diffExpandedId === item.id;
                const approveLabelForItem = isImport
                  ? r.approve_import
                  : isMapping
                    ? r.approve_mapping
                    : isVocabularyAlignment
                      ? r.approve_vocabulary_alignment
                    : isRemember
                      ? r.approve_fact
                      : isShacl || isUnmappedEntityType
                          ? r.acknowledge
                          : isLowConfidence
                          ? r.confirm_low_confidence
                          : isEntityCluster
                            ? r.promote_entity_cluster
                            : isWriteback
                            ? r.approve_writeback
                            : r.approve_merge;
                const itemDecisionIds = decisionIdsForReviewItem(events, item.id);
                return (
                  <li
                    key={item.id}
                    id={`review-item-${item.id}`}
                    className={cn(
                      'border-b border-border px-4 py-2.5 text-sm',
                      (focusItemId === item.id || highlightItemId === item.id) &&
                        'bg-muted ring-2 ring-primary ring-offset-2 ring-offset-background',
                    )}
                  >
                    <div className="text-[11px] text-muted-foreground">{kindLabel(item.kind)}</div>
                    <div className="mt-1 text-[13px] leading-snug">
                      {isImport
                        ? `${item.payload.filename ?? r.import_default_filename} (${fmt(r.import_byte_size, {
                            size:
                              item.payload.byte_size != null
                                ? formatLocaleNumber(locale as Locale, item.payload.byte_size)
                                : '?',
                          })})`
                        : isMapping
                          ? (
                            <span className="flex flex-col gap-1 font-mono text-xs">
                              <span>{item.payload.signature ?? emptyCell}</span>
                              <span className="text-muted-foreground">
                                → {item.payload.target_uri ?? emptyCell} (
                                {item.payload.target_kind ?? r.mapping_kind_unknown})
                              </span>
                            </span>
                          )
                          : isRemember
                            ? (
                              <span className="whitespace-pre-wrap">
                                {String(item.payload.content ?? item.payload.statement_id ?? emptyCell)}
                              </span>
                            )
                          : isLowConfidence
                            ? (
                              <span className="flex flex-col gap-2 text-xs text-muted-foreground">
                                <span>
                                  {fmt(r.low_confidence_line, {
                                    confidence: String(item.payload.confidence ?? emptyCell),
                                    threshold: String(item.payload.confidence_min ?? emptyCell),
                                    predicate: String(item.payload.surface_phrase ?? emptyCell),
                                  })}
                                </span>
                                {(() => {
                                  const qualityHref = reviewItemQualityHref(
                                    workspaceId,
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  const labelKey = reviewItemQualityLinkLabelKey(
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  if (!qualityHref || !labelKey) return null;
                                  return (
                                    <Button size="sm" variant="outline" className="h-7 w-fit text-xs" asChild>
                                      <Link to={qualityHref} data-testid={`review-quality-link-${item.id}`}>
                                        {r[labelKey]}
                                      </Link>
                                    </Button>
                                  );
                                })()}
                              </span>
                            )
                          : isVocabularyAlignment
                            ? (
                              <span className="flex flex-col gap-2 text-xs text-muted-foreground">
                                <span className="font-mono text-[11px] leading-snug">
                                  {reviewItemSummaryLine(
                                    item,
                                    r,
                                    locale as Locale,
                                    labels,
                                    emptyCell,
                                  )}
                                </span>
                                {(() => {
                                  const qualityHref = reviewItemQualityHref(
                                    workspaceId,
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  const labelKey = reviewItemQualityLinkLabelKey(
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  if (!qualityHref || !labelKey) return null;
                                  return (
                                    <Button size="sm" variant="outline" className="h-7 w-fit text-xs" asChild>
                                      <Link to={qualityHref} data-testid={`review-quality-link-${item.id}`}>
                                        {r[labelKey]}
                                      </Link>
                                    </Button>
                                  );
                                })()}
                              </span>
                            )
                          : isUnmappedEntityType
                            ? (
                              <span className="flex flex-col gap-2 text-xs text-muted-foreground">
                                <span>
                                  {fmt(r.unmapped_entity_type_line, {
                                    label: String(
                                      (item.payload as Record<string, unknown>).label ?? emptyCell,
                                    ),
                                  })}
                                </span>
                                {(() => {
                                  const suggestions = (item.payload as Record<string, unknown>)
                                    .vocabulary_alignment_suggestions;
                                  if (!Array.isArray(suggestions) || suggestions.length === 0) {
                                    return null;
                                  }
                                  return (
                                    <span className="text-[10px]">
                                      {fmt(r.unmapped_entity_type_l1_hint, {
                                        count: formatLocaleNumber(locale as Locale, suggestions.length),
                                      })}
                                    </span>
                                  );
                                })()}
                                {(() => {
                                  const qualityHref = reviewItemQualityHref(
                                    workspaceId,
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  const labelKey = reviewItemQualityLinkLabelKey(
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  if (!qualityHref || !labelKey) return null;
                                  return (
                                    <Button size="sm" variant="outline" className="h-7 w-fit text-xs" asChild>
                                      <Link to={qualityHref} data-testid={`review-quality-link-${item.id}`}>
                                        {r[labelKey]}
                                      </Link>
                                    </Button>
                                  );
                                })()}
                              </span>
                            )
                          : isEntityCluster
                            ? (
                              <span className="flex flex-col gap-1">
                                <span className="font-mono text-xs text-muted-foreground">
                                  {String(
                                    (item.payload as Record<string, unknown>).source ?? '',
                                  ) === 'graph_semantic_dedup'
                                    ? fmt(r.entity_cluster_semantic_line, {
                                        similarity: String(
                                          (item.payload as Record<string, unknown>).similarity ??
                                            emptyCell,
                                        ),
                                        count: formatLocaleNumber(
                                          locale as Locale,
                                          item.payload.entity_ids?.length ?? 0,
                                        ),
                                      })
                                    : fmt(r.entity_cluster_line, {
                                        label: String(item.payload.canonical_label ?? emptyCell),
                                        count: formatLocaleNumber(
                                          locale as Locale,
                                          item.payload.entity_ids?.length ?? 0,
                                        ),
                                      })}
                                </span>
                                <p className="text-[10px] text-muted-foreground">{r.entity_cluster_pick_hint}</p>
                                <ul
                                  className="mt-1 flex flex-col gap-1.5 text-xs text-muted-foreground"
                                  data-testid={`review-cluster-pick-${item.id}`}
                                >
                                  {(item.payload.entity_ids ?? []).map((entityId) => {
                                    const inputId = `cluster-primary-${item.id}-${entityId}`;
                                    return (
                                      <li key={entityId}>
                                        <label
                                          htmlFor={inputId}
                                          className="flex cursor-pointer items-start gap-2 rounded-md border border-border px-2 py-1.5 has-[:checked]:border-primary has-[:checked]:bg-muted/50"
                                        >
                                          <input
                                            id={inputId}
                                            type="radio"
                                            name={`cluster-primary-${item.id}`}
                                            className="mt-0.5"
                                            checked={clusterPrimary[item.id] === entityId}
                                            onChange={() =>
                                              setClusterPrimary((prev) => ({
                                                ...prev,
                                                [item.id]: entityId,
                                              }))
                                            }
                                          />
                                          <span>{renderReadableEntity(entityId)}</span>
                                        </label>
                                      </li>
                                    );
                                  })}
                                </ul>
                              </span>
                            )
                          : isShacl
                            ? (
                              <span className="flex flex-col gap-2">
                                {item.payload.subject_id ? (
                                  <p className="text-xs text-foreground">
                                    <span className="text-muted-foreground">{r.conflict_subject}: </span>
                                    {renderReadableEntity(String(item.payload.subject_id))}
                                  </p>
                                ) : null}
                                <p className="text-xs text-muted-foreground">
                                  {fmt(r.shacl_violation_line, {
                                    message: String(
                                      (item.payload as { message?: string }).message ?? emptyCell,
                                    ),
                                  })}
                                </p>
                                {(item.payload as { predicate_iri?: string }).predicate_iri ? (
                                  <p className="text-[10px] text-muted-foreground">
                                    {fmt(r.conflict_predicate_mapped, {
                                      iri: String((item.payload as { predicate_iri?: string }).predicate_iri),
                                    })}
                                  </p>
                                ) : null}
                                {(item.payload as { ontology_uri?: string }).ontology_uri ? (
                                  <p className="text-[10px] text-muted-foreground">
                                    {fmt(r.shacl_hub_ontology, {
                                      uri: String((item.payload as { ontology_uri?: string }).ontology_uri),
                                    })}
                                  </p>
                                ) : null}
                                {(() => {
                                  const qualityHref = reviewItemQualityHref(
                                    workspaceId,
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  const labelKey = reviewItemQualityLinkLabelKey(
                                    item.kind,
                                    item.payload as Record<string, unknown>,
                                  );
                                  if (!qualityHref || !labelKey) return null;
                                  return (
                                    <Button size="sm" variant="outline" className="h-7 w-fit text-xs" asChild>
                                      <Link to={qualityHref} data-testid={`review-quality-link-${item.id}`}>
                                        {r[labelKey]}
                                      </Link>
                                    </Button>
                                  );
                                })()}
                                <p className="text-[10px] text-muted-foreground">{r.shacl_ack_hint}</p>
                              </span>
                            )
                          : isWriteback
                            ? (
                              <span className="flex flex-col gap-1.5" data-testid={`review-writeback-diff-${item.id}`}>
                                <span className="font-mono text-xs text-muted-foreground">
                                  {item.payload.provider ?? emptyCell} · {item.payload.external_table ?? emptyCell} (
                                  {item.payload.external_pk ?? emptyCell})
                                </span>
                                {item.payload.changes ? (
                                  <span className="flex flex-col gap-1 rounded-md border border-border bg-muted/40 p-2 font-mono text-xs">
                                    {Object.entries(item.payload.changes).map(([col, chg]) => (
                                      <span key={col} className="flex flex-wrap items-center gap-1.5">
                                        <span className="font-semibold text-foreground">{col}:</span>
                                        <span className="line-through text-muted-foreground">
                                          {String(chg?.old ?? emptyCell)}
                                        </span>
                                        <span className="text-muted-foreground">→</span>
                                        <span className="font-medium text-primary">
                                          {String(chg?.new ?? emptyCell)}
                                        </span>
                                      </span>
                                    ))}
                                  </span>
                                ) : null}
                              </span>
                            )
                          : (
                          <span className="flex flex-col gap-1">
                            <span className="text-muted-foreground text-xs font-normal">
                              {r.primary}
                            </span>
                            {primaryId !== emptyCell ? renderNodeRef(primaryId) : emptyCell}
                            {duplicateIds.length ? (
                              <>
                                <span className="text-muted-foreground text-xs font-normal pt-1">
                                  {r.duplicates}
                                </span>
                                <span className="flex flex-col gap-1">
                                  {duplicateIds.map((dup) => (
                                    <span key={dup}>{renderNodeRef(dup)}</span>
                                  ))}
                                </span>
                              </>
                            ) : null}
                          </span>
                        )}
                    </div>
                    {!isImport && !isMapping && !isRemember && !isShacl && !isWriteback ? (
                      <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">{r.graph_only_merge_hint}</p>
                    ) : null}
                    {isEntityMerge && primaryId !== emptyCell && firstDuplicate ? (
                      <>
                        <Button
                          type="button"
                          variant="link"
                          className="mt-2 h-auto gap-1 p-0 text-[11px] text-foreground"
                          onClick={() =>
                            setDiffExpandedId(showDiff ? null : item.id)
                          }
                        >
                          {showDiff ? (
                            <PublicIcon name="chevron-down" size={12} />
                          ) : (
                            <PublicIcon name="chevron-right" size={12} />
                          )}
                          {r.property_diff}
                        </Button>
                        {showDiff ? (
                          <EntityMergePropertyDiff
                            workspaceId={workspaceId}
                            primaryId={primaryId}
                            duplicateId={firstDuplicate}
                            variant="compact"
                          />
                        ) : null}
                      </>
                    ) : null}
                    {isMapping ? (
                      <div className="mt-2">
                        <Link
                          to={workspaceOntologyHubPath(workspaceId, 'statement')}
                          className="text-[11px] text-foreground underline-offset-2 hover:underline"
                        >
                          {r.open_mappings}
                        </Link>
                      </div>
                    ) : null}
                    <p className="mt-2 text-[10px] leading-relaxed text-muted-foreground">
                      {r.governance_approve_hint}{' '}
                      <Link
                        to={activityLogBrowseDecisionsPath(workspaceId)}
                        className="text-foreground underline-offset-2 hover:underline"
                      >
                        {r.open_decisions_workspace}
                      </Link>
                    </p>
                    {renderDecisionLinks(itemDecisionIds, 'review-item-decision')}
                    {(focusItemId === item.id || highlightItemId === item.id) &&
                    itemDecisionIds.length > 0 ? (
                      <ReviewDecisionNarrative
                        workspaceId={workspaceId}
                        decisionId={itemDecisionIds.at(-1)!}
                        variant="embedded"
                      />
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        className="h-8"
                        disabled={busyId === item.id}
                        onClick={() => void resolve(item.id, 'approve')}
                      >
                        {busyId === item.id ? (
                          <PublicIcon name="loader-01" size={12} className="animate-spin" />
                        ) : (
                          <PublicIcon name="check-01" size={12} />
                        )}
                        {approveLabelForItem}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="h-8"
                        disabled={busyId === item.id}
                        onClick={() => void resolve(item.id, 'reject')}
                      >
                        <PublicIcon name="x-02" size={12} />
                        {r.reject}
                      </Button>
                    </div>
                  </li>
                );
              })}
              {hasMore ? (
                <li className="border-b border-border px-4 py-3">
                  <div
                    ref={loadMoreSentinelRef}
                    className="flex items-center justify-center gap-2 text-[11px] text-muted-foreground"
                  >
                    {loadingMore ? (
                      <>
                        <PublicIcon name="loader-01" size={14} className="animate-spin" />
                        {r.loading_more}
                      </>
                    ) : (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-[11px]"
                        onClick={() => void loadMore()}
                      >
                        {r.load_more}
                      </Button>
                    )}
                  </div>
                </li>
              ) : null}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
