import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DataPanelToolbar } from '@/components/app/shared/console/index.js';
import { MiniStatCard } from '@/components/app/shared/console/MiniStatCard.js';
import { DatePicker } from '@/components/app/shared/primitives/date-picker.js';
import { EntityRefLine } from '@/components/app/shared/workspace/entity-ref-line.js';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { Card } from '@/components/ui/card.js';
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Separator } from '@/components/ui/separator.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { formatLocaleDateTime, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { Label } from '@/components/ui/label.js';
import { graphPath, graphDiffPreviewPath } from '@/modules/workspace/graph/lib/graph-url-state.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { workspaceGraphDiffPath } from '@/lib/nav/nav-config.js';
import { toast } from 'sonner';
import {
  calendarDateFromIso,
  endOfLocalDayIso,
  startOfLocalDay,
  startOfLocalDayIso,
} from '@/modules/workspace/graph/lib/temporal/day-range.js';
import { parseInstantMs } from '@/modules/workspace/graph/lib/temporal/instant.js';
import { resolveScrubberBounds } from '@/modules/workspace/graph/lib/temporal/scrubber-bounds.js';
import { cn } from '@/lib/utils.js';
import { basisSessionFetch } from '@/lib/session/basis-session-fetch.js';
import { workspaceApiPath } from '@/lib/workspace/api-path.js';
import { buildGraphAuditPack, triggerJsonFileDownload } from '@/modules/workspace/graph/lib/graph-audit-pack.js';

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
    <section className="space-y-2.5">
      <div className="flex items-center gap-2">
        <h4 className="text-xs font-semibold text-foreground">{title}</h4>
        <Badge variant={count > 0 ? 'secondary' : 'outline'} className="text-[11px] font-normal tabular-nums">
          {count}
        </Badge>
      </div>
      {count > 0 ? (
        <ul className="space-y-2">{children}</ul>
      ) : (
        <p className="text-xs text-muted-foreground">{emptyLabel}</p>
      )}
    </section>
  );
}

function NodeListItem({
  nodeId,
  labels,
  href,
  suffix,
}: {
  nodeId: string;
  labels: Record<string, string | null>;
  href: string;
  suffix?: string;
}) {
  return (
    <li className="rounded-lg border border-border/70 bg-muted/15 px-3 py-2.5 text-sm transition-colors hover:bg-muted/25">
      <Link to={href} className="block min-w-0 underline-offset-2 hover:text-primary hover:underline">
        <EntityRefLine id={nodeId} labels={labels} className="min-w-0" />
      </Link>
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
  const [auditPackBusy, setAuditPackBusy] = useState(false);
  const autoCompareRef = useRef(false);

  const now = useMemo(() => new Date(), []);
  const { minBound, maxBound } = useMemo(
    () =>
      resolveScrubberBounds({
        minDate: ledgerBounds?.min,
        maxDate: ledgerBounds?.max,
        now,
      }),
    [ledgerBounds?.max, ledgerBounds?.min, now],
  );
  const minDay = startOfLocalDay(minBound);
  const maxDay = startOfLocalDay(maxBound);
  const disabledMatchers = [{ before: minDay }, { after: maxDay }];

  const fromDay = fromTime.trim() ? calendarDateFromIso(fromTime) : undefined;
  const toDay = toTime.trim() ? calendarDateFromIso(toTime) : undefined;

  function onSelectFrom(day: Date | undefined) {
    if (!day) return;
    const fromIso = startOfLocalDayIso(day);
    setFromTime(fromIso);
    const toMs = parseInstantMs(toTime);
    const fromMs = parseInstantMs(fromIso);
    if (toMs === null || fromMs === null || toMs < fromMs) {
      setToTime(endOfLocalDayIso(day));
    }
  }

  function onSelectTo(day: Date | undefined) {
    if (!day) return;
    const toIso = endOfLocalDayIso(day);
    const toMs = parseInstantMs(toIso);
    const fromMs = parseInstantMs(fromTime);
    if (fromMs !== null && toMs !== null && toMs < fromMs) {
      setFromTime(startOfLocalDayIso(day));
    }
    setToTime(toIso);
  }

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

  const nodeGraphHref = (nodeId: string) =>
    graphPath(workspaceId, { focus: nodeId, at: graphAtForDiff || undefined });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runDiff();
  }

  const canCompare = Boolean(fromTime.trim() && toTime.trim()) && !loading;
  const changeTotal = diff ? diffChangeTotal(diff.summary) : 0;

  return (
    <div className={cn('basis-graph-diff-page flex min-h-0 flex-col gap-4', className)}>
      <form onSubmit={(e) => void onSubmit(e)}>
        <DataPanelToolbar
          className="flex-wrap gap-y-2"
          search={
            <div className="flex flex-wrap items-center gap-2" role="group" aria-label={g.time_range}>
              <div className="flex items-center gap-1.5">
                <Label
                  htmlFor="graph-diff-from-date"
                  className="shrink-0 text-xs font-medium text-muted-foreground"
                >
                  {g.from_date_label}
                </Label>
                <DatePicker
                  id="graph-diff-from-date"
                  value={fromDay}
                  onChange={onSelectFrom}
                  placeholder={g.pick_date}
                  disabled={loading || boundsLoading}
                  disabledMatchers={disabledMatchers}
                  defaultMonth={fromDay ?? minDay}
                  startMonth={minDay}
                  endMonth={maxDay}
                  className="h-9 w-[8.5rem] shrink-0 text-xs"
                />
              </div>
              <span className="text-xs text-muted-foreground" aria-hidden>
                →
              </span>
              <div className="flex items-center gap-1.5">
                <Label
                  htmlFor="graph-diff-to-date"
                  className="shrink-0 text-xs font-medium text-muted-foreground"
                >
                  {g.to_date_label}
                </Label>
                <DatePicker
                  id="graph-diff-to-date"
                  value={toDay}
                  onChange={onSelectTo}
                  placeholder={g.pick_date}
                  disabled={loading || boundsLoading}
                  disabledMatchers={disabledMatchers}
                  defaultMonth={toDay ?? maxDay}
                  startMonth={minDay}
                  endMonth={maxDay}
                  className="h-9 w-[8.5rem] shrink-0 text-xs"
                />
              </div>
            </div>
          }
          actions={
            <Button type="submit" size="sm" className="min-w-[5rem]" disabled={!canCompare}>
              {loading ? <Spinner className="size-4" /> : null}
              {g.compare}
            </Button>
          }
        />
      </form>

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
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 bg-muted/15 px-4 py-2.5 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{g.resolved_range}</span>
              <span className="font-mono text-muted-foreground">
                {formatLocaleDateTime(loc, diff.from_time)} → {formatLocaleDateTime(loc, diff.to_time)}
              </span>
            </div>
            {changeTotal > 0 ? (
              <div className="flex flex-wrap items-center gap-1.5" data-testid="graph-diff-merge-studio">
                <Button type="button" variant="outline" size="sm" className="h-7 text-xs" asChild>
                  <Link
                    to={graphDiffPreviewPath(workspaceId, diff.from_time, diff.to_time)}
                    data-testid="graph-diff-preview-on-graph"
                  >
                    {g.preview_on_graph}
                  </Link>
                </Button>
                {graphAtForDiff ? (
                  <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" asChild>
                    <Link
                      to={graphPath(workspaceId, { at: graphAtForDiff, timeline: true })}
                      data-testid="graph-diff-open-graph-timeline-at-end"
                    >
                      {g.graph_at_end_timeline_link}
                    </Link>
                  </Button>
                ) : null}
                <Button type="button" variant="ghost" size="sm" className="h-7 text-xs" onClick={() => void copyComparisonLink()}>
                  {g.studio_copy_link}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs"
                  data-testid="graph-diff-copy-staging-manifest"
                  onClick={() => void copyStagingManifest()}
                >
                  {g.copy_staging_manifest}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs"
                  data-testid="graph-diff-download-audit-pack"
                  disabled={auditPackBusy}
                  onClick={() => void downloadAuditPack()}
                >
                  {auditPackBusy ? t.graph.import_export.preparing : g.download_audit_pack}
                </Button>
              </div>
            ) : null}
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

          {changeTotal === 0 ? (
            <Empty className="border border-dashed border-border bg-muted/20 py-10">
              <EmptyHeader>
                <EmptyTitle>{g.no_changes_title}</EmptyTitle>
                <EmptyDescription>{g.no_changes_description}</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <Card className="gap-0 py-0">
              <Tabs defaultValue="nodes" className="w-full">
                <div className="border-b border-border/60 px-4 pt-2">
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
                </div>

                <TabsContent value="nodes" className="m-0 p-4">
                  <div className="space-y-5">
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
                        />
                      ))}
                    </DiffSection>
                  </div>
                </TabsContent>

                <TabsContent value="edges" className="m-0 p-4">
                  <div className="space-y-5">
                    <DiffSection
                      title={g.added_edges_title}
                      count={diff.added_edges.length}
                      emptyLabel={g.none}
                    >
                      {diff.added_edges.map((edge, index) => (
                        <li
                          key={`${edge.source_id}-${edge.target_id}-${edge.type ?? ''}-${index}`}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 bg-muted/15 px-3 py-2.5 text-sm"
                        >
                          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                            <Link
                              to={nodeGraphHref(edge.source_id)}
                              className="min-w-0 hover:text-primary hover:underline"
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
                              className="min-w-0 hover:text-primary hover:underline"
                            >
                              <EntityRefLine
                                id={edge.target_id}
                                labels={nodeLabels}
                                className="inline min-w-0"
                              />
                            </Link>
                          </div>
                          {edge.type ? (
                            <Badge variant="outline" className="font-mono text-[11px] font-normal">
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
                          className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/70 px-3 py-2.5 text-sm text-muted-foreground"
                        >
                          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                            <EntityRefLine
                              id={edge.source_id}
                              labels={nodeLabels}
                              className="inline min-w-0"
                            />
                            <span className="mx-1">→</span>
                            <EntityRefLine
                              id={edge.target_id}
                              labels={nodeLabels}
                              className="inline min-w-0"
                            />
                          </div>
                          {edge.type ? (
                            <Badge variant="outline" className="font-mono text-[11px] font-normal">
                              {edge.type}
                            </Badge>
                          ) : null}
                        </li>
                      ))}
                    </DiffSection>
                  </div>
                </TabsContent>
              </Tabs>
            </Card>
          )}
        </div>
      ) : null}
    </div>
  );
}
