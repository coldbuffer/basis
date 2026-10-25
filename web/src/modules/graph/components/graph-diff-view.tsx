import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MiniStatCard } from '@/components/app/shared/console/MiniStatCard.js';
import { EntityRefLine } from '@/components/app/shared/workspace/entity-ref-line.js';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card.js';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty.js';
import { TemporalRangePicker } from './temporal-range-picker.js';
import { FieldGroup } from '@/components/ui/field.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Separator } from '@/components/ui/separator.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { formatLocaleDateTime, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { workspaceOpenApiGET, workspaceOpenApiPOST, workspaceOpenApiPUT } from '@/lib/openapi/client.js';
import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import { graphPath } from '@/modules/graph/lib/graph-url-state.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { graphDiffPreviewPath, graphImportDialogPath } from '@/modules/graph/lib/graph-url-state.js';
import { workspaceGraphDiffPath, workspacePath, workspaceReviewPath } from '@/lib/nav/nav-config.js';
import { toast } from 'sonner';
import { searchPath } from '@/modules/search/lib/search-url-state.js';
import { endOfLocalDayIso, startOfLocalDayIso } from '@/modules/graph/lib/temporal/day-range.js';
import { resolveScrubberBounds } from '@/modules/graph/lib/temporal/scrubber-bounds.js';
import { cn } from '@/lib/utils.js';
import {
  clearGraphStagingDraft,
  readGraphStagingDraft,
  writeGraphStagingDraft,
} from '@/modules/graph/lib/graph-staging-draft.js';
import { basisSessionFetch } from '@/lib/session/basis-session-fetch.js';
import { workspaceApiPath } from '@/lib/workspace/api-path.js';
import { buildGraphAuditPack, triggerJsonFileDownload } from '@/modules/graph/lib/graph-audit-pack.js';

type GraphDiffResponse = {
  from_time: string;
  to_time: string;
  added_nodes: string[];
  removed_nodes: string[];
  modified_nodes: Array<{ id: string; change: string }>;
  added_edges: Array<{ source_id: string; target_id: string; type?: string }>;
  removed_edges: Array<{ source_id: string; target_id: string; type?: string }>;
  summary: {
    nodes_added: number;
    nodes_removed: number;
    nodes_modified: number;
    edges_added: number;
    edges_removed: number;
  };
};

function diffChangeTotal(summary: GraphDiffResponse['summary']): number {
  return (
    summary.nodes_added +
    summary.nodes_removed +
    summary.nodes_modified +
    summary.edges_added +
    summary.edges_removed
  );
}

function collectNodeIds(diff: GraphDiffResponse): string[] {
  const ids = new Set<string>();
  for (const id of diff.added_nodes) ids.add(id);
  for (const id of diff.removed_nodes) ids.add(id);
  for (const row of diff.modified_nodes) ids.add(row.id);
  for (const edge of diff.added_edges) {
    ids.add(edge.source_id);
    ids.add(edge.target_id);
  }
  for (const edge of diff.removed_edges) {
    ids.add(edge.source_id);
    ids.add(edge.target_id);
  }
  return [...ids];
}

function DiffSection({
  title,
  count,
  children,
  emptyLabel,
}: {
  title: string;
  count: number;
  children: ReactNode;
  emptyLabel: string;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2">
        <h4 className="text-sm font-semibold text-foreground">{title}</h4>
        <Badge variant={count > 0 ? 'secondary' : 'outline'} className="tabular-nums">
          {count}
        </Badge>
      </div>
      {count > 0 ? (
        <ul className="space-y-2">{children}</ul>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      )}
    </section>
  );
}

function NodeListItem({
  nodeId,
  labels,
  href,
  suffix,
  mergePickActions,
}: {
  nodeId: string;
  labels: Record<string, string | null>;
  href: string;
  suffix?: string;
  mergePickActions?: { onPrimary: () => void; onDuplicate: () => void; labels: { primary: string; duplicate: string } };
}) {
  return (
    <li className="rounded-md border border-border/80 bg-muted/30 px-3 py-2 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <Link to={href} className="block min-w-0 flex-1 hover:underline">
          <EntityRefLine id={nodeId} labels={labels} className="min-w-0" />
        </Link>
        {mergePickActions ? (
          <div className="flex shrink-0 flex-wrap gap-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-[11px]"
              data-testid={`graph-diff-merge-primary-${nodeId}`}
              onClick={mergePickActions.onPrimary}
            >
              {mergePickActions.labels.primary}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-[11px]"
              data-testid={`graph-diff-merge-duplicate-${nodeId}`}
              onClick={mergePickActions.onDuplicate}
            >
              {mergePickActions.labels.duplicate}
            </Button>
          </div>
        ) : null}
      </div>
      {suffix ? (
        <p className="mt-1 font-mono text-[11px] text-muted-foreground">{suffix}</p>
      ) : null}
    </li>
  );
}

export function GraphDiff({
  workspaceId,
  className,
  initialFrom,
  initialTo,
}: {
  workspaceId: string;
  className?: string;
  initialFrom?: string;
  initialTo?: string;
}) {
  const { t, locale } = useI18n();
  const g = t.graph.diff;
  const loc = locale as Locale;
  const [, setSearchParams] = useSearchParams();
  const [fromTime, setFromTime] = useState(initialFrom ?? '');
  const [toTime, setToTime] = useState(initialTo ?? '');
  const [ledgerBounds, setLedgerBounds] = useState<{ min?: string; max?: string } | null>(null);
  const [boundsLoading, setBoundsLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [diff, setDiff] = useState<GraphDiffResponse | null>(null);
  const [stagingManifest, setStagingManifest] = useState<Record<string, unknown> | null>(null);
  const [mergePrimaryId, setMergePrimaryId] = useState('');
  const [mergeDuplicateId, setMergeDuplicateId] = useState('');
  const [mergeBusy, setMergeBusy] = useState(false);
  const [auditPackBusy, setAuditPackBusy] = useState(false);
  const autoCompareRef = useRef(false);
  const stagingDraftRestoredRef = useRef(false);
  const { caps } = useWorkspaceCapabilities();
  const canProposeMerge = Boolean(caps?.graph_write);
  const stagingSessionKey =
    typeof stagingManifest?.session_key === 'string'
      ? stagingManifest.session_key.trim()
      : '';

  useEffect(() => {
    let cancelled = false;
    setBoundsLoading(true);
    void (async () => {
      try {
        const bounds = await workspaceOpenApiGET<{ min?: string; max?: string }>(workspaceId, 'temporal/bounds');
        if (cancelled) return;
        setLedgerBounds(bounds);
        const resolved = resolveScrubberBounds({
          minDate: bounds.min,
          maxDate: bounds.max,
          now: new Date(),
        });
        if (!initialFrom) {
          setFromTime((prev) => prev || startOfLocalDayIso(resolved.minBound));
        }
        if (!initialTo) {
          setToTime((prev) => prev || endOfLocalDayIso(resolved.maxBound));
        }
      } catch {
        if (!cancelled) setLedgerBounds(null);
      } finally {
        if (!cancelled) setBoundsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initialFrom, initialTo, workspaceId]);

  const runDiff = useCallback(async () => {
    if (!fromTime.trim() || !toTime.trim()) return;
    setLoading(true);
    setError('');
    setDiff(null);
    setStagingManifest(null);
    try {
      const data = await workspaceOpenApiGET<{ diff: GraphDiffResponse; manifest: Record<string, unknown> }>(
        workspaceId,
        'graph/staging',
        {
          params: { query: { from: fromTime.trim(), to: toTime.trim() } },
        },
      );
      setDiff(data.diff);
      setStagingManifest(data.manifest);
      setSearchParams({ from: fromTime.trim(), to: toTime.trim() }, { replace: true });
    } catch (err) {
      setError(formatUserFacingApiError(err, loc));
    } finally {
      setLoading(false);
    }
  }, [fromTime, workspaceId, loc, setSearchParams, toTime]);

  useEffect(() => {
    if (autoCompareRef.current) return;
    if (!initialFrom?.trim() || !initialTo?.trim()) return;
    autoCompareRef.current = true;
    void runDiff();
  }, [initialFrom, initialTo, runDiff]);

  useEffect(() => {
    stagingDraftRestoredRef.current = false;
  }, [stagingSessionKey]);

  useEffect(() => {
    if (!stagingSessionKey || stagingDraftRestoredRef.current) return;
    const localDraft = readGraphStagingDraft(stagingSessionKey);
    const serverDraft = (stagingManifest?.draft ?? null) as
      | { primary?: string; duplicate?: string }
      | null;
    stagingDraftRestoredRef.current = true;
    const primary = localDraft?.primary || serverDraft?.primary || '';
    const duplicate = localDraft?.duplicate || serverDraft?.duplicate || '';
    if (primary) setMergePrimaryId(primary);
    if (duplicate) setMergeDuplicateId(duplicate);
  }, [stagingManifest?.draft, stagingSessionKey]);

  useEffect(() => {
    if (!stagingSessionKey) return;
    writeGraphStagingDraft(stagingSessionKey, {
      primary: mergePrimaryId,
      duplicate: mergeDuplicateId,
    });
    if (canProposeMerge) {
      void workspaceOpenApiPUT(workspaceId, `graph/staging/${encodeURIComponent(stagingSessionKey)}/draft`, {
        body: {
          from_time: fromTime.trim(),
          to_time: toTime.trim(),
          primary: mergePrimaryId.trim(),
          duplicate: mergeDuplicateId.trim(),
        },
      }).catch(() => {});
    }
  }, [canProposeMerge, fromTime, workspaceId, mergeDuplicateId, mergePrimaryId, stagingSessionKey, toTime]);

  const labelIds = useMemo(() => (diff ? collectNodeIds(diff) : []), [diff]);
  const nodeLabels = useWorkspaceNodeLabels(workspaceId, labelIds);

  const graphAtForDiff = diff ? diff.to_time?.trim() || toTime.trim() : toTime.trim();

  async function copyComparisonLink() {
    if (!diff) return;
    const href = `${window.location.origin}${workspaceGraphDiffPath(workspaceId, diff.from_time, diff.to_time)}`;
    try {
      await navigator.clipboard.writeText(href);
      toast.success(t.core.common.copySuccess);
    } catch {
      toast.error(t.core.common.copyFailed);
    }
  }

  async function copyStagingManifest() {
    if (!stagingManifest || !diff) return;
    const payload = { manifest: stagingManifest, diff };
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      toast.success(g.copy_staging_success);
    } catch {
      toast.error(t.core.common.copyFailed);
    }
  }

  async function downloadAuditPack() {
    if (!stagingManifest || !diff) return;
    const rawFocus = stagingManifest.focus_node_ids;
    const focusNodeIds = Array.isArray(rawFocus)
      ? rawFocus.filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
      : undefined;
    setAuditPackBusy(true);
    try {
      const pack = await buildGraphAuditPack({
        workspaceId,
        nodeIds: focusNodeIds,
        staging: { manifest: stagingManifest, diff },
        postExport: (body) =>
          basisSessionFetch(workspaceApiPath(workspaceId, 'export'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          }),
        getAudit: () =>
          workspaceOpenApiGET<{ events: unknown[] }>(workspaceId, 'audit/graph-mutations', {
            params: { query: { limit: 100, action_prefix: 'workspace.graph.' } },
          }),
        getProjection: () => workspaceOpenApiGET(workspaceId, 'graph/projection'),
      });
      triggerJsonFileDownload('basis_graph_audit_pack.json', pack);
      toast.success(t.graph.import_export.audit_pack_success);
    } catch (err) {
      toast.error(formatUserFacingApiError(err, loc));
    } finally {
      setAuditPackBusy(false);
    }
  }

  async function proposeEntityMerge(event: FormEvent) {
    event.preventDefault();
    const primary = mergePrimaryId.trim();
    const duplicate = mergeDuplicateId.trim();
    if (!primary || !duplicate || primary === duplicate) return;
    setMergeBusy(true);
    try {
      await workspaceOpenApiPOST(workspaceId, 'graph/staging/entity-merge', {
        body: { primary_id: primary, duplicate_ids: [duplicate] },
      });
      toast.success(g.propose_merge_success);
      if (stagingSessionKey) clearGraphStagingDraft(stagingSessionKey);
      setMergePrimaryId('');
      setMergeDuplicateId('');
    } catch (err) {
      toast.error(formatUserFacingApiError(err, loc));
    } finally {
      setMergeBusy(false);
    }
  }
  const nodeGraphHref = (nodeId: string) =>
    graphPath(workspaceId, { focus: nodeId, at: graphAtForDiff || undefined });

  const mergePickActionLabels = {
    primary: g.propose_merge_use_primary,
    duplicate: g.propose_merge_use_duplicate,
  };
  const mergePickForNode = (nodeId: string) =>
    canProposeMerge
      ? {
          labels: mergePickActionLabels,
          onPrimary: () => setMergePrimaryId(nodeId),
          onDuplicate: () => setMergeDuplicateId(nodeId),
        }
      : undefined;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runDiff();
  }

  function applyLedgerBounds() {
    const resolved = resolveScrubberBounds({
      minDate: ledgerBounds?.min,
      maxDate: ledgerBounds?.max,
      now: new Date(),
    });
    setFromTime(startOfLocalDayIso(resolved.minBound));
    setToTime(endOfLocalDayIso(resolved.maxBound));
  }

  const canCompare = Boolean(fromTime.trim() && toTime.trim()) && !loading;
  const changeTotal = diff ? diffChangeTotal(diff.summary) : 0;
  const toTimeTrimmed = toTime.trim();

  return (
    <div className={cn('basis-graph-diff-page flex min-h-0 flex-col gap-4', className)}>
      <Card className="gap-0 py-0">
        <CardHeader className="border-b px-4 py-4 sm:px-6">
          <CardTitle className="text-base">{g.time_range}</CardTitle>
          <CardDescription className="space-y-1">
            <span>{g.compare_hint}</span>
            <span className="block text-[11px] text-muted-foreground" data-testid="graph-diff-temporal-hint">
              {g.temporal_compare_hint}
            </span>
          </CardDescription>
        </CardHeader>
        <form onSubmit={(e) => void onSubmit(e)}>
          <CardContent className="px-4 py-4 sm:px-6">
            <FieldGroup className="gap-4">
              <TemporalRangePicker
                fromTime={fromTime}
                toTime={toTime}
                onFromChange={setFromTime}
                onToChange={setToTime}
                ledgerMin={ledgerBounds?.min}
                ledgerMax={ledgerBounds?.max}
                boundsLoading={boundsLoading}
                disabled={loading}
              />
            </FieldGroup>
          </CardContent>
          <CardFooter className="flex flex-wrap items-center gap-2 border-t px-4 py-3 sm:px-6">
            <Button type="submit" size="sm" disabled={!canCompare}>
              {loading ? <Spinner className="size-4" /> : null}
              {g.compare}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={boundsLoading || ledgerBounds === null}
              onClick={applyLedgerBounds}
            >
              {boundsLoading ? <Spinner className="size-4" /> : null}
              {g.use_full_range}
            </Button>
            <Button type="button" size="sm" variant="ghost" asChild>
              <Link to={workspacePath(workspaceId, 'graph')}>{g.graph_link}</Link>
            </Button>
            {toTimeTrimmed ? (
              <>
                <Button type="button" size="sm" variant="ghost" asChild>
                  <Link
                    to={graphPath(workspaceId, { at: graphAtForDiff, timeline: true })}
                    data-testid="graph-diff-open-graph-timeline-at-end"
                  >
                    {g.graph_at_end_timeline_link}
                  </Link>
                </Button>
                <Button type="button" size="sm" variant="ghost" asChild>
                  <Link to={searchPath(workspaceId, { scope: 'graph', at: graphAtForDiff })}>
                    {g.search_link}
                  </Link>
                </Button>
              </>
            ) : null}
          </CardFooter>
        </form>
      </Card>

      {error ? (
        <Alert variant="destructive">
          <PublicIcon name="alert-circle" size={16} />
          <AlertTitle>{t.core.common.loadFailed}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {loading && !diff ? (
        <div className="flex items-center justify-center py-16">
          <Spinner className="size-6" />
        </div>
      ) : null}

      {!loading && !diff && !error ? (
        <Empty className="border border-dashed border-border bg-muted/20">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <PublicIcon name="git-diff" size={24} />
            </EmptyMedia>
            <EmptyTitle>{g.empty_title}</EmptyTitle>
            <EmptyDescription>{g.empty_description}</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            {boundsLoading ? (
              <p className="text-muted-foreground text-xs">{g.bounds_loading}</p>
            ) : null}
          </EmptyContent>
        </Empty>
      ) : null}

      {diff ? (
        <div className="flex flex-col gap-4 pb-2">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{g.resolved_range}</span>
            <span className="font-mono">
              {formatLocaleDateTime(loc, diff.from_time)} → {formatLocaleDateTime(loc, diff.to_time)}
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <MiniStatCard
              icon={<PublicIcon name="plus-01" size={18} />}
              tint="var(--ok)"
              tintBg="var(--ok-soft)"
              value={formatLocaleNumber(loc, diff.summary.nodes_added)}
              label={g.stat_nodes_added}
            />
            <MiniStatCard
              icon={<PublicIcon name="minus" size={18} />}
              tint="var(--bad)"
              tintBg="var(--bad-soft)"
              value={formatLocaleNumber(loc, diff.summary.nodes_removed)}
              label={g.stat_nodes_removed}
            />
            <MiniStatCard
              icon={<PublicIcon name="edit-01" size={18} />}
              tint="var(--info)"
              tintBg="var(--info-soft)"
              value={formatLocaleNumber(loc, diff.summary.nodes_modified)}
              label={g.stat_nodes_modified}
            />
            <MiniStatCard
              icon={<PublicIcon name="link" size={18} />}
              tint="var(--ok)"
              tintBg="var(--ok-soft)"
              value={formatLocaleNumber(loc, diff.summary.edges_added)}
              label={g.stat_edges_added}
            />
            <MiniStatCard
              icon={<PublicIcon name="minus" size={18} />}
              tint="var(--bad)"
              tintBg="var(--bad-soft)"
              value={formatLocaleNumber(loc, diff.summary.edges_removed)}
              label={g.stat_edges_removed}
            />
          </div>

          {changeTotal > 0 ? (
            <Alert data-testid="graph-diff-staging-steps">
              <PublicIcon name="check-square-contained" size={16} />
              <AlertTitle>{g.staging_steps_title}</AlertTitle>
              <AlertDescription className="text-muted-foreground">{g.staging_steps_body}</AlertDescription>
            </Alert>
          ) : null}

          {changeTotal > 0 ? (
            <Alert data-testid="graph-diff-merge-studio">
              <PublicIcon name="shield-01" size={16} />
              <AlertTitle>{g.studio_title}</AlertTitle>
              <AlertDescription className="text-muted-foreground">{g.studio_description}</AlertDescription>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link to={workspaceReviewPath(workspaceId)}>{g.studio_open_review}</Link>
                </Button>
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link to={graphImportDialogPath(workspaceId)} data-testid="graph-diff-open-import">
                    {g.studio_open_import}
                  </Link>
                </Button>
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link
                    to={`${workspacePath(workspaceId, 'settings')}?tab=graph`}
                    data-testid="graph-diff-open-export"
                  >
                    {g.studio_open_export}
                  </Link>
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => void copyComparisonLink()}>
                  {g.studio_copy_link}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid="graph-diff-copy-staging-manifest"
                  onClick={() => void copyStagingManifest()}
                >
                  {g.copy_staging_manifest}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid="graph-diff-download-audit-pack"
                  disabled={auditPackBusy}
                  onClick={() => void downloadAuditPack()}
                >
                  {auditPackBusy ? t.graph.import_export.preparing : g.download_audit_pack}
                </Button>
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link
                    to={graphDiffPreviewPath(workspaceId, diff.from_time, diff.to_time)}
                    data-testid="graph-diff-preview-on-graph"
                  >
                    {g.preview_on_graph}
                  </Link>
                </Button>
              </div>
              {canProposeMerge ? (
                <form
                  className="mt-4 space-y-2 border-t border-border/60 pt-3"
                  data-testid="graph-diff-propose-merge-form"
                  onSubmit={(event) => void proposeEntityMerge(event)}
                >
                  <p className="text-xs font-medium text-foreground">{g.propose_merge_title}</p>
                  <p className="text-xs text-muted-foreground">{g.propose_merge_hint}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="graph-diff-merge-primary" className="text-xs">
                        {g.propose_merge_primary}
                      </Label>
                      <Input
                        id="graph-diff-merge-primary"
                        className="h-8 font-mono text-xs"
                        value={mergePrimaryId}
                        onChange={(event) => setMergePrimaryId(event.target.value)}
                        placeholder={g.propose_merge_primary_placeholder}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="graph-diff-merge-duplicate" className="text-xs">
                        {g.propose_merge_duplicate}
                      </Label>
                      <Input
                        id="graph-diff-merge-duplicate"
                        className="h-8 font-mono text-xs"
                        value={mergeDuplicateId}
                        onChange={(event) => setMergeDuplicateId(event.target.value)}
                        placeholder={g.propose_merge_duplicate_placeholder}
                      />
                    </div>
                  </div>
                  <Button
                    type="submit"
                    variant="outline"
                    size="sm"
                    disabled={mergeBusy || !mergePrimaryId.trim() || !mergeDuplicateId.trim()}
                    data-testid="graph-diff-propose-merge-submit"
                  >
                    {mergeBusy ? t.core.common.loading : g.propose_merge_submit}
                  </Button>
                </form>
              ) : null}
            </Alert>
          ) : null}

          {changeTotal === 0 ? (
            <Empty className="border border-dashed border-border bg-muted/20 py-10">
              <EmptyHeader>
                <EmptyTitle>{g.no_changes_title}</EmptyTitle>
                <EmptyDescription>{g.no_changes_description}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Tabs defaultValue="nodes">
              <TabsList variant="line" className="w-full justify-start">
                <TabsTrigger value="nodes">
                  {g.tab_nodes}
                  <Badge variant="secondary" className="ml-2 tabular-nums">
                    {formatLocaleNumber(
                      loc,
                      diff.summary.nodes_added +
                        diff.summary.nodes_removed +
                        diff.summary.nodes_modified,
                    )}
                  </Badge>
                </TabsTrigger>
                <TabsTrigger value="edges">
                  {g.tab_edges}
                  <Badge variant="secondary" className="ml-2 tabular-nums">
                    {formatLocaleNumber(loc, diff.summary.edges_added + diff.summary.edges_removed)}
                  </Badge>
                </TabsTrigger>
              </TabsList>

              <TabsContent value="nodes" className="mt-4">
                <div className="rounded-lg border border-border p-4">
                  <div className="space-y-6">
                    <DiffSection
                      title={g.added_nodes_title}
                      count={diff.added_nodes.length}
                      emptyLabel={g.none}
                    >
                      {diff.added_nodes.map((id) => (
                        <NodeListItem
                          key={id}
                          nodeId={id}
                          labels={nodeLabels}
                          href={nodeGraphHref(id)}
                          mergePickActions={mergePickForNode(id)}
                        />
                      ))}
                    </DiffSection>
                    <Separator />
                    <DiffSection
                      title={g.removed_nodes_title}
                      count={diff.removed_nodes.length}
                      emptyLabel={g.none}
                    >
                      {diff.removed_nodes.map((id) => (
                        <NodeListItem
                          key={id}
                          nodeId={id}
                          labels={nodeLabels}
                          href={nodeGraphHref(id)}
                        />
                      ))}
                    </DiffSection>
                    <Separator />
                    <DiffSection
                      title={g.modified_nodes_title}
                      count={diff.modified_nodes.length}
                      emptyLabel={g.none}
                    >
                      {diff.modified_nodes.map((row) => (
                        <NodeListItem
                          key={row.id}
                          nodeId={row.id}
                          labels={nodeLabels}
                          href={nodeGraphHref(row.id)}
                          suffix={row.change}
                          mergePickActions={mergePickForNode(row.id)}
                        />
                      ))}
                    </DiffSection>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="edges" className="mt-4">
                <div className="rounded-lg border border-border p-4">
                  <div className="space-y-6">
                    <DiffSection
                      title={g.added_edges_title}
                      count={diff.added_edges.length}
                      emptyLabel={g.none}
                    >
                      {diff.added_edges.map((edge, index) => (
                        <li
                          key={`${edge.source_id}-${edge.target_id}-${edge.type ?? ''}-${index}`}
                          className="rounded-md border border-border/80 bg-muted/30 px-3 py-2 text-sm"
                        >
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Link
                              to={nodeGraphHref(edge.source_id)}
                              className="min-w-0 hover:underline"
                            >
                              <EntityRefLine
                                id={edge.source_id}
                                labels={nodeLabels}
                                className="inline min-w-0"
                              />
                            </Link>
                            <PublicIcon name="arrow-right" size={14} className="shrink-0 text-muted-foreground" />
                            <Link
                              to={nodeGraphHref(edge.target_id)}
                              className="min-w-0 hover:underline"
                            >
                              <EntityRefLine
                                id={edge.target_id}
                                labels={nodeLabels}
                                className="inline min-w-0"
                              />
                            </Link>
                          </div>
                          {edge.type ? (
                            <Badge variant="outline" className="mt-2 font-mono text-[10px]">
                              {edge.type}
                            </Badge>
                          ) : null}
                        </li>
                      ))}
                    </DiffSection>
                    <Separator />
                    <DiffSection
                      title={g.removed_edges_title}
                      count={diff.removed_edges.length}
                      emptyLabel={g.none}
                    >
                      {diff.removed_edges.map((edge, index) => (
                        <li
                          key={`${edge.source_id}-${edge.target_id}-${edge.type ?? ''}-${index}`}
                          className="rounded-md border border-border/80 px-3 py-2 text-sm text-muted-foreground"
                        >
                          <EntityRefLine
                            id={edge.source_id}
                            labels={nodeLabels}
                            className="inline min-w-0"
                          />
                          <span className="mx-1.5">→</span>
                          <EntityRefLine
                            id={edge.target_id}
                            labels={nodeLabels}
                            className="inline min-w-0"
                          />
                          {edge.type ? (
                            <Badge variant="outline" className="ml-2 font-mono text-[10px]">
                              {edge.type}
                            </Badge>
                          ) : null}
                        </li>
                      ))}
                    </DiffSection>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          )}
        </div>
      ) : null}
    </div>
  );
}
