import { useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { GraphHost } from '@/modules/workspace/graph/pages/graph-host.js';
import {
  graphPath,
  mergeGraphAtParam,
  parseGraphDiffPreviewParams,
} from '@/modules/workspace/graph/lib/graph-url-state.js';

export function GraphPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const focus = searchParams.get('focus');
  const at = searchParams.get('at');
  const openTimeline = searchParams.get('timeline') === '1';
  const openImportDialog = searchParams.get('import') === '1';
  const openExportDialog = searchParams.get('export') === '1';
  const diffPreview = parseGraphDiffPreviewParams(searchParams.toString());
  const focusAtInstant = at ?? diffPreview?.diffTo;

  const onScrubberAtChange = useCallback(
    (atIso: string) => {
      setSearchParams((prev) => mergeGraphAtParam(prev.toString(), atIso), { replace: true });
    },
    [setSearchParams],
  );

  if (!id) {
    return null;
  }

  const timelineEntryHref = !openTimeline
    ? graphPath(id, {
        ...(focus ? { focus } : {}),
        ...(at ? { at } : {}),
        timeline: true,
      })
    : undefined;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <GraphHost
        workspaceId={id}
        focusNodeId={focus}
        focusAtInstant={focusAtInstant}
        diffPreview={diffPreview ?? undefined}
        openTimelinePanel={openTimeline}
        timelineEntryHref={timelineEntryHref}
        openImportDialog={openImportDialog}
        openExportDialog={openExportDialog}
        onScrubberAtChange={onScrubberAtChange}
      />
    </div>
  );
}
