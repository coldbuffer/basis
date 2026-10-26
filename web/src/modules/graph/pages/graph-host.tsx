import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkspaceHostProvider } from '@/lib/workspace/ws-http.js';
import { buildWorkspaceHttpConfig } from '@/lib/workspace/ws-host.js';
import { GraphDiffPreviewBar } from '../components/graph-diff-preview-bar.js';
import { GraphRebuildButton } from '@/modules/graph/components/graph-rebuild-button.js';
import { graphDiffOverlayFromResponse, emptyGraphDiffOverlay } from '@/modules/graph/lib/graph-diff-overlay.js';
import {
  applyGraphDiffMergePick,
  emptyGraphDiffMergePick,
  graphDiffMergePickReady,
  isGraphDiffMergeCandidate,
  type GraphDiffMergePick,
  type GraphDiffMergePickSlot,
} from '@/modules/graph/lib/graph-diff-merge-pick.js';
import type { GraphDiffPreviewParams } from '@/modules/graph/lib/graph-url-state.js';
import { mergeGraphDiffFocusParam } from '@/modules/graph/lib/graph-url-state.js';
import { useWorkspaceGraphDiff } from '@/modules/graph/lib/use-graph-diff.js';
import { workspaceOpenApiPOST } from '@/lib/openapi/client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { toast } from 'sonner';
import {
  clearGraphStagingDraft,
  readGraphStagingDraft,
  writeGraphStagingDraft,
} from '@/modules/graph/lib/graph-staging-draft.js';
import { ImportExportDialog } from '@/modules/graph/components/import-export/import-export-dialog.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { Button } from '@/components/ui/button.js';
import { SIDEBAR_ICON_BUTTON_CLASS, SidebarIcon } from '@/components/app/shared/shell/sidebar-icon.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { GraphWsThemeSync } from '@/modules/graph/lib/graph/graph-ws-theme-sync.js';
import { workspaceGraphDiffPath } from '@/lib/nav/nav-config.js';
import { searchPath } from '@/modules/search/lib/search-url-state.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import { Label } from '@/components/ui/label.js';
import {
  loadGraphIncludeArchived,
  saveGraphIncludeArchived,
} from '@/modules/graph/lib/graph-include-archived-pref.js';
const GraphScreen = lazy(() =>
  import('@/modules/graph/pages/screen.js').then((module) => ({
    default: module.GraphScreen,
  })),
);

const graphQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function GraphHost({
  workspaceId,
  focusNodeId,
  focusAtInstant,
  openTimelinePanel,
  timelineEntryHref,
  openImportDialog,
  openExportDialog,
  diffPreview,
  onScrubberAtChange,
}: {
  workspaceId: string;
  focusNodeId?: string | null;
  focusAtInstant?: string | null;
  openTimelinePanel?: boolean;
  /** Deep link to open temporal playback (`?timeline=1`, F-TIM-04). */
  timelineEntryHref?: string;
  /** Deep link `?import=1` / `?export=1` (F-IO / F-DIFF staging path). */
  openImportDialog?: boolean;
  openExportDialog?: boolean;
  diffPreview?: GraphDiffPreviewParams;
  onScrubberAtChange?: (atIso: string) => void;
}) {
  const { t, locale } = useI18n();
  const g = t.graph.page;
  const gd = t.graph.diff;
  const apiLocale = locale as Locale;
  const [, setSearchParams] = useSearchParams();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();
  const [mergePick, setMergePick] = useState<GraphDiffMergePick>(() => emptyGraphDiffMergePick());
  const [mergePickSlot, setMergePickSlot] = useState<GraphDiffMergePickSlot>('primary');
  const mergePickSlotRef = useRef(mergePickSlot);
  mergePickSlotRef.current = mergePickSlot;
  const [mergeBusy, setMergeBusy] = useState(false);
  const config = useMemo(() => buildWorkspaceHttpConfig(workspaceId, apiLocale), [apiLocale, workspaceId]);
  const [importExportOpen, setImportExportOpen] = useState(false);
  const [importExportFocus, setImportExportFocus] = useState<'import' | 'export'>('export');
  const [reloadToken, setReloadToken] = useState(0);
  const [includeArchivedProjection, setIncludeArchivedProjection] = useState(() =>
    loadGraphIncludeArchived(workspaceId),
  );

  useEffect(() => {
    setIncludeArchivedProjection(loadGraphIncludeArchived(workspaceId));
  }, [workspaceId]);
  const deepLinkDialogOpenedRef = useRef(false);

  useEffect(() => {
    if (deepLinkDialogOpenedRef.current) return;
    if (openImportDialog) {
      deepLinkDialogOpenedRef.current = true;
      setImportExportFocus('import');
      setImportExportOpen(true);
    } else if (openExportDialog) {
      deepLinkDialogOpenedRef.current = true;
      setImportExportFocus('export');
      setImportExportOpen(true);
    }
  }, [openExportDialog, openImportDialog]);

  const focusToken = useMemo(() => {
    if (!focusNodeId) return undefined;
    let hash = 0;
    for (let i = 0; i < focusNodeId.length; i += 1) {
      hash = (hash * 31 + focusNodeId.charCodeAt(i)) | 0;
    }
    return Math.abs(hash) || 1;
  }, [focusNodeId]);

  if (!capsLoading && caps && !caps.graph) {
    return <WorkspaceUnavailable workspaceId={workspaceId} feature="graph" />;
  }

  function openImportExport(focus: 'import' | 'export') {
    setImportExportFocus(focus);
    setImportExportOpen(true);
  }

  const canImportExport = !capsLoading && caps?.import_export;
  const canRebuild = !capsLoading && caps?.graph_write;

  const graphAt = focusAtInstant?.trim() || undefined;
  const graphSearchHref = searchPath(workspaceId, { scope: 'graph', ...(graphAt ? { at: graphAt } : {}) });

  const diffFrom = diffPreview?.diffFrom;
  const diffTo = diffPreview?.diffTo;
  const {
    diff: graphDiff,
    stagingSessionKey,
    loading: graphDiffLoading,
    error: graphDiffError,
  } = useWorkspaceGraphDiff(workspaceId, diffFrom, diffTo, apiLocale);
  const stagingDraftRestoredRef = useRef(false);
  const diffOverlay = useMemo(() => {
    if (!graphDiff) return emptyGraphDiffOverlay();
    return graphDiffOverlayFromResponse(graphDiff, focusNodeId);
  }, [focusNodeId, graphDiff]);

  const canProposeMerge = Boolean(diffPreview && !capsLoading && caps?.graph_write);

  useEffect(() => {
    if (!diffPreview) {
      setMergePick(emptyGraphDiffMergePick());
      setMergePickSlot('primary');
      stagingDraftRestoredRef.current = false;
    }
  }, [diffPreview?.diffFrom, diffPreview?.diffTo]);

  useEffect(() => {
    stagingDraftRestoredRef.current = false;
  }, [stagingSessionKey]);

  useEffect(() => {
    if (!stagingSessionKey || stagingDraftRestoredRef.current) return;
    const draft = readGraphStagingDraft(stagingSessionKey);
    stagingDraftRestoredRef.current = true;
    if (!draft) return;
    setMergePick({
      primary: draft.primary,
      duplicate: draft.duplicate,
    });
    if (draft.primary && !draft.duplicate) setMergePickSlot('duplicate');
  }, [stagingSessionKey]);

  useEffect(() => {
    if (!stagingSessionKey) return;
    writeGraphStagingDraft(stagingSessionKey, mergePick);
  }, [mergePick, stagingSessionKey]);

  const onDiffPreviewNodeSelect = useCallback(
    (nodeId: string) => {
      if (!diffPreview || !graphDiff) return;
      setSearchParams(
        (prev) => mergeGraphDiffFocusParam(prev.toString(), nodeId),
        { replace: true },
      );
      if (!canProposeMerge) return;
      if (!isGraphDiffMergeCandidate(nodeId, graphDiff)) {
        toast.message(g.diff_preview_merge_not_candidate);
        return;
      }
      setMergePick((pick) => {
        const applied = applyGraphDiffMergePick(pick, nodeId, mergePickSlotRef.current);
        mergePickSlotRef.current = applied.nextSlot;
        setMergePickSlot(applied.nextSlot);
        return applied.pick;
      });
    },
    [canProposeMerge, diffPreview, g.diff_preview_merge_not_candidate, graphDiff, setSearchParams],
  );

  const submitDiffPreviewMerge = useCallback(async () => {
    if (!graphDiffMergePickReady(mergePick)) return;
    setMergeBusy(true);
    try {
      await workspaceOpenApiPOST(workspaceId, 'graph/staging/entity-merge', {
        body: {
          primary_id: mergePick.primary.trim(),
          duplicate_ids: [mergePick.duplicate.trim()],
        },
      });
      toast.success(gd.propose_merge_success);
      if (stagingSessionKey) clearGraphStagingDraft(stagingSessionKey);
      setMergePick(emptyGraphDiffMergePick());
      setMergePickSlot('primary');
    } catch (err) {
      toast.error(formatUserFacingApiError(err, apiLocale));
    } finally {
      setMergeBusy(false);
    }
  }, [apiLocale, gd.propose_merge_success, workspaceId, mergePick]);

  const graphDataActions = (
    <>
      {timelineEntryHref ? (
        <Button
          type="button"
          variant="outline"
          size="icon-sm"
          className={SIDEBAR_ICON_BUTTON_CLASS}
          aria-label={g.open_timeline}
          title={g.open_timeline}
          asChild
        >
          <Link to={timelineEntryHref} data-testid="workspace-graph-open-timeline">
            <SidebarIcon name="clock-backward" />
          </Link>
        </Button>
      ) : null}
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        className={SIDEBAR_ICON_BUTTON_CLASS}
        aria-label={g.search_graph}
        title={g.search_graph}
        asChild
      >
        <Link to={graphSearchHref} data-testid="workspace-graph-open-search">
          <SidebarIcon name="search-01" />
        </Link>
      </Button>
      <div className="flex max-w-[11rem] items-center gap-2 rounded-md border border-border px-2 py-1">
        <Checkbox
          id="graph-include-archived"
          checked={includeArchivedProjection}
          onCheckedChange={(checked) => {
            const enabled = checked === true;
            setIncludeArchivedProjection(enabled);
            saveGraphIncludeArchived(workspaceId, enabled);
            setReloadToken((token) => token + 1);
          }}
        />
        <Label htmlFor="graph-include-archived" className="text-xs font-normal leading-tight">
          {g.include_archived_projection}
        </Label>
      </div>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        className={SIDEBAR_ICON_BUTTON_CLASS}
        aria-label={g.graph_diff}
        title={g.graph_diff}
        asChild
      >
        <Link
          to={workspaceGraphDiffPath(workspaceId, graphAt, graphAt)}
          data-testid="workspace-graph-open-diff"
        >
          <SidebarIcon name="git-diff" />
        </Link>
      </Button>
      {canRebuild || canImportExport ? (
          <>
            {canRebuild ? (
              <GraphRebuildButton
                workspaceId={workspaceId}
                iconOnly
                onRebuilt={() => setReloadToken((token) => token + 1)}
              />
            ) : null}
            {canImportExport ? (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  className={SIDEBAR_ICON_BUTTON_CLASS}
                  aria-label={g.import}
                  title={g.import}
                  onClick={() => openImportExport('import')}
                >
                  <SidebarIcon name="upload-01" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon-sm"
                  className={SIDEBAR_ICON_BUTTON_CLASS}
                  aria-label={g.export}
                  title={g.export}
                  onClick={() => openImportExport('export')}
                >
                  <SidebarIcon name="download-01" />
                </Button>
              </>
            ) : null}
          </>
        ) : null}
    </>
  );

  return (
    <div
      className="basis-graph-canvas relative flex min-h-0 w-full flex-1 flex-col overflow-hidden bg-background text-foreground"
      data-workspace-id={workspaceId}
      data-testid="workspace-graph-canvas"
    >
      <ImportExportDialog
        workspaceId={workspaceId}
        open={importExportOpen}
        onOpenChange={setImportExportOpen}
        focus={importExportFocus}
        seedNodeIds={focusNodeId?.trim() ? [focusNodeId.trim()] : undefined}
      />

      <QueryClientProvider client={graphQueryClient}>
        <WorkspaceHostProvider config={config}>
          <div className="flex h-full min-h-0 flex-1 flex-col">
            {diffPreview ? (
              <GraphDiffPreviewBar
                workspaceId={workspaceId}
                diffFrom={diffPreview.diffFrom}
                diffTo={diffPreview.diffTo}
                diff={graphDiff}
                loading={graphDiffLoading}
                error={graphDiffError}
                canProposeMerge={canProposeMerge}
                mergePick={mergePick}
                mergePickSlot={mergePickSlot}
                onMergePickSlotChange={setMergePickSlot}
                onClearMergePick={() => {
                  setMergePick(emptyGraphDiffMergePick());
                  setMergePickSlot('primary');
                }}
                mergeBusy={mergeBusy}
                onSubmitMerge={() => void submitDiffPreviewMerge()}
              />
            ) : null}
            <Suspense
              fallback={
                <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
                  <Spinner className="size-4" />
                  {t.graph.page.loading_graph}
                </div>
              }
            >
              <GraphWsThemeSync>
              <GraphScreen
                key={workspaceId}
                workspaceId={workspaceId}
                externalFocusNodeId={focusNodeId ?? undefined}
                externalFocusToken={focusToken}
                externalTemporalAt={focusAtInstant ?? undefined}
                externalOpenTemporalPanel={openTimelinePanel}
                onScrubberAtChange={onScrubberAtChange}
                graphDataActions={graphDataActions}
                graphWriteEnabled={!capsLoading && (caps?.graph_write ?? false)}
                decisionsEnabled={!capsLoading && (caps?.decisions ?? false)}
                externalReloadToken={reloadToken}
                includeArchivedProjection={includeArchivedProjection}
                apiErrorLocale={apiLocale}
                externalDiffOverlay={diffPreview ? diffOverlay : null}
                onNodeSelectNotify={diffPreview ? onDiffPreviewNodeSelect : undefined}
              />
              </GraphWsThemeSync>
            </Suspense>
          </div>
        </WorkspaceHostProvider>
      </QueryClientProvider>
    </div>
  );
}
