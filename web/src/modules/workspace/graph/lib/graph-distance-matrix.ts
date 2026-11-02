/** Use server hop matrix when in-memory BFS over the loaded graph is too heavy. */
export const GRAPH_STRUCTURAL_DISTANCE_LOCAL_MAX_NODES = 2500;

/** Cap nodes sent to `POST .../graph/distance-matrix` (pairwise path work on server). */
export const GRAPH_DISTANCE_MATRIX_MAX_NODES = 320;

export type DistanceMatrixApiResponse = {
  nodes: string[];
  metric: string;
  matrix: Array<Array<number | null>>;
};

export function shouldUseServerStructuralDistance(nodeCount: number): boolean {
  return nodeCount > GRAPH_STRUCTURAL_DISTANCE_LOCAL_MAX_NODES;
}

export function collectDistanceMatrixNodeIds(
  graph: { nodes: () => Iterable<string>; hasNode: (id: string) => boolean },
  anchorNodeId: string,
  maxNodes: number = GRAPH_DISTANCE_MATRIX_MAX_NODES,
): string[] {
  if (!graph.hasNode(anchorNodeId)) {
    return [];
  }
  const ids: string[] = [anchorNodeId];
  for (const nodeId of graph.nodes()) {
    if (ids.length >= maxNodes) {
      break;
    }
    const stable = String(nodeId);
    if (stable === anchorNodeId) {
      continue;
    }
    ids.push(stable);
  }
  return ids;
}

/** Hop distances from anchor along the matrix row indexed by `anchorNodeId`. */
export function structuralDistancesFromMatrixResponse(
  response: DistanceMatrixApiResponse,
  anchorNodeId: string,
  maxHops: number,
): Record<string, number> {
  const anchorIndex = response.nodes.findIndex((id) => id === anchorNodeId);
  if (anchorIndex < 0) {
    return {};
  }
  const row = response.matrix[anchorIndex];
  if (!row) {
    return {};
  }
  const distances: Record<string, number> = {};
  response.nodes.forEach((nodeId, col) => {
    const raw = row[col];
    if (raw == null || !Number.isFinite(raw)) {
      return;
    }
    const hops = Math.max(0, Math.round(raw));
    if (hops <= maxHops) {
      distances[nodeId] = hops;
    }
  });
  return distances;
}
