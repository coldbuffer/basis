import { useEffect, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import {
  diffFocusEntries,
  nextDiffFocusIndex,
} from '@/modules/workspace/graph/lib/diff/graph-diff-focus.js';
import {
  clearGraphDiffPreviewParams,
  mergeGraphDiffFocusParam,
  parseGraphUrlState,
} from '@/modules/workspace/graph/lib/graph-url-state.js';
import type { GraphDiffPayload } from '@/modules/workspace/graph/lib/diff/use-graph-diff.js';
import { workspaceGraphDiffPath } from '@/lib/nav/nav-config.js';
import {
  graphDiffMergePickReady,
  type GraphDiffMergePick,
  type GraphDiffMergePickSlot,
} from '@/modules/workspace/graph/lib/diff/graph-diff-merge-pick.js';
import { cn } from '@/lib/utils.js';

function changeTotal(summary: GraphDiffPayload['summary']): number {
  return (
    summary.nodes_added +
    summary.nodes_removed +
    summary.nodes_modified +
    summary.edges_added +
    summary.edges_removed
  );
}

/** Read-only diff overlay banner on the graph canvas (F-DIFF-01 staging preview). */
export function GraphDiffPreviewBar({
  workspaceId,
  diffFrom,
  diffTo,
  diff,
  loading,
  error,
  canProposeMerge = false,
  mergePick,
  mergePickSlot = 'primary',
  onMergePickSlotChange,
  onClearMergePick,
  mergeBusy = false,
  onSubmitMerge,
}: {
  workspaceId: string;
  diffFrom: string;
  diffTo: string;
  diff: GraphDiffPayload | null;
  loading: boolean;
  error: string | null;
  canProposeMerge?: boolean;
  mergePick?: GraphDiffMergePick;
  mergePickSlot?: GraphDiffMergePickSlot;
  onMergePickSlotChange?: (slot: GraphDiffMergePickSlot) => void;
  onClearMergePick?: () => void;
  mergeBusy?: boolean;
  onSubmitMerge?: () => void;
}) {
  const { t, locale } = useI18n();
  const g = t.graph.page;
  const [searchParams, setSearchParams] = useSearchParams();
  const graphUrl = parseGraphUrlState(searchParams.toString());

  const total = useMemo(() => (diff ? changeTotal(diff.summary) : 0), [diff]);
  const focusEntries = useMemo(
    () => (diff ? diffFocusEntries(diff) : []),
    [diff],
  );
  const focusIndex = useMemo(() => {
    const focus = graphUrl.focus?.trim();
    if (!focus || focusEntries.length === 0) return -1;
    const idx = focusEntries.findIndex((e) => e.nodeId === focus);
    return idx >= 0 ? idx : 0;
  }, [focusEntries, graphUrl.focus]);
  const activeFocus =
    focusIndex >= 0 && focusEntries[focusIndex] ? focusEntries[focusIndex] : null;

  useEffect(() => {
    if (focusEntries.length === 0 || graphUrl.focus?.trim()) return;
    const first = focusEntries[0]!.nodeId;
    setSearchParams(
      (prev) => mergeGraphDiffFocusParam(prev.toString(), first),
      { replace: true },
    );
  }, [focusEntries, graphUrl.focus, setSearchParams]);

  function cycleFocus(delta: number) {
    if (focusEntries.length === 0) return;
    const base = focusIndex >= 0 ? focusIndex : 0;
    const nextIdx = nextDiffFocusIndex(base, delta, focusEntries.length);
    const next = focusEntries[nextIdx]!;
    setSearchParams(
      (prev) => mergeGraphDiffFocusParam(prev.toString(), next.nodeId),
      { replace: true },
    );
  }

  function dismiss() {
    setSearchParams((prev) => clearGraphDiffPreviewParams(prev.toString()), { replace: true });
  }

  return (
    <Alert
      className="mx-3 mt-2 shrink-0 border-primary/25 bg-primary/5"
      data-testid="workspace-graph-diff-preview-bar"
    >
      <PublicIcon name="git-diff" size={16} className="text-primary" />
      <AlertTitle className="text-sm">{g.diff_preview_title}</AlertTitle>
      <AlertDescription className="space-y-2 text-xs text-muted-foreground">
        {loading ? (
          <span className="inline-flex items-center gap-2">
            <Spinner className="size-3.5" />
            {t.core.common.loading}
          </span>
        ) : error ? (
          <span className="text-destructive">{error}</span>
        ) : diff ? (
          <span data-testid="workspace-graph-diff-preview-summary">
            {fmt(g.diff_preview_summary, {
              total: formatLocaleNumber(locale as Locale, total),
              added: formatLocaleNumber(locale as Locale, diff.summary.nodes_added),
              removed: formatLocaleNumber(locale as Locale, diff.summary.nodes_removed),
            })}
          </span>
        ) : null}
        {diff && !loading && !error ? (
          <p className="flex flex-wrap items-center gap-3 text-[11px] text-foreground">
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-[#5BC986]" aria-hidden />
              {g.diff_preview_legend_added}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-[#8FE7FF]" aria-hidden />
              {g.diff_preview_legend_modified}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-3 rounded bg-[#5BC986]" aria-hidden />
              {g.diff_preview_legend_added_edges}
            </span>
            <span className="text-muted-foreground">{g.diff_preview_legend_removed_hint}</span>
          </p>
        ) : null}
        {canProposeMerge && diff && !loading && !error ? (
          <div
            className="space-y-2 rounded-md border border-border/70 bg-background/60 p-2"
            data-testid="workspace-graph-diff-preview-merge-pick"
          >
            <p className="text-xs font-medium text-foreground">{g.diff_preview_merge_title}</p>
            <p className="text-[11px] text-muted-foreground">{g.diff_preview_merge_hint}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant={mergePickSlot === 'primary' ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                data-testid="workspace-graph-diff-merge-pick-primary"
                onClick={() => onMergePickSlotChange?.('primary')}
              >
                {g.diff_preview_merge_pick_primary}
              </Button>
              <Button
                type="button"
                variant={mergePickSlot === 'duplicate' ? 'default' : 'outline'}
                size="sm"
                className="h-7 text-xs"
                data-testid="workspace-graph-diff-merge-pick-duplicate"
                onClick={() => onMergePickSlotChange?.('duplicate')}
              >
                {g.diff_preview_merge_pick_duplicate}
              </Button>
            </div>
            <div className="grid gap-1 font-mono text-[11px] text-foreground sm:grid-cols-2">
              <span>
                {g.diff_preview_merge_primary_label}:{' '}
                <span className={cn(!mergePick?.primary && 'text-muted-foreground')}>
                  {mergePick?.primary?.trim() || t.core.common.emptyCell}
                </span>
              </span>
              <span>
                {g.diff_preview_merge_duplicate_label}:{' '}
                <span className={cn(!mergePick?.duplicate && 'text-muted-foreground')}>
                  {mergePick?.duplicate?.trim() || t.core.common.emptyCell}
                </span>
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                data-testid="workspace-graph-diff-merge-clear"
                disabled={!mergePick?.primary && !mergePick?.duplicate}
                onClick={() => onClearMergePick?.()}
              >
                {g.diff_preview_merge_clear}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                data-testid="workspace-graph-diff-merge-submit"
                disabled={mergeBusy || !mergePick || !graphDiffMergePickReady(mergePick)}
                onClick={() => onSubmitMerge?.()}
              >
                {mergeBusy ? t.core.common.loading : g.diff_preview_merge_submit}
              </Button>
            </div>
          </div>
        ) : null}
        {activeFocus ? (
          <p className="font-mono text-[11px] text-foreground" data-testid="workspace-graph-diff-preview-focus">
            {fmt(g.diff_preview_focus_line, {
              index: formatLocaleNumber(locale as Locale, focusIndex + 1),
              total: formatLocaleNumber(locale as Locale, focusEntries.length),
              change: g.diff_preview_change_label[activeFocus.change],
              nodeId: activeFocus.nodeId,
            })}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2 pt-0.5">
          {focusEntries.length > 0 ? (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                data-testid="workspace-graph-diff-preview-focus-prev"
                onClick={() => cycleFocus(-1)}
              >
                {g.diff_preview_focus_prev}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                data-testid="workspace-graph-diff-preview-focus-next"
                onClick={() => cycleFocus(1)}
              >
                {g.diff_preview_focus_next}
              </Button>
            </>
          ) : null}
          <Button type="button" variant="outline" size="sm" className="h-7 text-xs" asChild>
            <Link
              to={workspaceGraphDiffPath(workspaceId, diffFrom.trim(), diffTo.trim())}
              data-testid="workspace-graph-diff-preview-open-full"
            >
              {g.diff_preview_open_full}
            </Link>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={dismiss}
            data-testid="workspace-graph-diff-preview-dismiss"
          >
            {g.diff_preview_dismiss}
          </Button>
        </div>
      </AlertDescription>
    </Alert>
  );
}
