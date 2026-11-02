import type Graph from "graphology";

export type GraphEdgeTypeCount = {
  type: string;
  count: number;
};

const FALLBACK_EDGE_TYPE = "related_to";

export function edgeTypeOf(
  attributes: { edgeType?: string; dominantEdgeType?: string } | undefined,
): string {
  const type = attributes?.edgeType || attributes?.dominantEdgeType;
  return typeof type === "string" && type.trim() ? type.trim() : FALLBACK_EDGE_TYPE;
}

export function isEdgeTypeSuppressed(edgeType: string | undefined, hiddenTypes: ReadonlySet<string>): boolean {
  if (hiddenTypes.size === 0) {
    return false;
  }
  const type = edgeType && edgeType.trim() ? edgeType.trim() : FALLBACK_EDGE_TYPE;
  return hiddenTypes.has(type);
}

export function collectEdgeTypeCounts(graph: Graph): GraphEdgeTypeCount[] {
  const counts = new Map<string, number>();
  graph.forEachEdge((_id, attributes) => {
    const type = edgeTypeOf(attributes as { edgeType?: string; dominantEdgeType?: string });
    counts.set(type, (counts.get(type) ?? 0) + 1);
  });
  return sortEdgeTypeCounts([...counts.entries()].map(([type, count]) => ({ type, count })));
}

/** Keep loaded-graph types, and append types that only appear on the display graph. */
export function mergeEdgeTypeCounts(
  base: GraphEdgeTypeCount[],
  extra: GraphEdgeTypeCount[],
): GraphEdgeTypeCount[] {
  const seen = new Set(base.map((item) => item.type));
  const merged = [...base];
  for (const item of extra) {
    if (!seen.has(item.type)) {
      merged.push(item);
    }
  }
  return sortEdgeTypeCounts(merged);
}

function sortEdgeTypeCounts(items: GraphEdgeTypeCount[]): GraphEdgeTypeCount[] {
  return [...items].sort((left, right) => right.count - left.count || left.type.localeCompare(right.type));
}
