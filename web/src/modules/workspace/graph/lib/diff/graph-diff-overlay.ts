import type { GraphDiffFocusResponse } from '@/modules/workspace/graph/lib/diff/graph-diff-focus.js';

export type GraphDiffEdgeRecord = {
  source_id: string;
  target_id: string;
  type?: string;
};

export type GraphDiffOverlayInput = GraphDiffFocusResponse & {
  added_edges?: GraphDiffEdgeRecord[];
};

export type GraphDiffOverlayState = {
  enabled: boolean;
  added: ReadonlySet<string>;
  modified: ReadonlySet<string>;
  addedEdgeKeys: ReadonlySet<string>;
  focusNodeId?: string;
};

/** Match keys used by `basis/domain/explorer/graph_diff._edge_key`. */
export function graphDiffEdgeKey(
  sourceId: string,
  targetId: string,
  edgeType: string,
): string {
  return [sourceId, targetId, edgeType].join('|');
}

export function graphDiffOverlayFromResponse(
  diff: GraphDiffOverlayInput,
  focusNodeId?: string | null,
): GraphDiffOverlayState {
  const addedEdgeKeys = new Set(
    (diff.added_edges ?? []).map((edge) =>
      graphDiffEdgeKey(edge.source_id, edge.target_id, edge.type ?? ''),
    ),
  );
  return {
    enabled: true,
    added: new Set(diff.added_nodes),
    modified: new Set(diff.modified_nodes.map((row) => row.id)),
    addedEdgeKeys,
    focusNodeId: focusNodeId?.trim() || undefined,
  };
}

export function emptyGraphDiffOverlay(): GraphDiffOverlayState {
  return {
    enabled: false,
    added: new Set(),
    modified: new Set(),
    addedEdgeKeys: new Set(),
  };
}

export function graphDiffEdgeTouchesChange(
  sourceId: string,
  targetId: string,
  overlay: GraphDiffOverlayState,
): boolean {
  return (
    overlay.added.has(sourceId) ||
    overlay.added.has(targetId) ||
    overlay.modified.has(sourceId) ||
    overlay.modified.has(targetId)
  );
}
