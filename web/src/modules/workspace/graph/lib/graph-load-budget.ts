export type GraphLoadBudget = {
  maxNodes: number;
  maxEdges: number;
};

export type GraphCatalogTotals = {
  nodeTotal: number | null;
  edgeTotal: number | null;
};

export const GRAPH_LOAD_BUDGET_MIN_NODES = 1;
export const GRAPH_LOAD_BUDGET_MIN_EDGES = 1;

const DEFAULT_BUDGET_NODES = 200;
const DEFAULT_BUDGET_EDGES = 400;

export function catalogNodeCeiling(totals: GraphCatalogTotals): number {
  if (totals.nodeTotal != null) {
    return Math.max(0, totals.nodeTotal);
  }
  return DEFAULT_BUDGET_NODES;
}

export function catalogEdgeCeiling(totals: GraphCatalogTotals): number {
  if (totals.edgeTotal != null) {
    return Math.max(0, totals.edgeTotal);
  }
  return DEFAULT_BUDGET_EDGES;
}

export function loadBudgetSliderBounds(ceiling: number, minFloor: number) {
  if (ceiling <= 0) {
    return { min: 0, max: 0, step: 1, disabled: true };
  }
  const min = Math.min(minFloor, ceiling);
  const range = ceiling - min;
  return {
    min,
    max: ceiling,
    step: 1,
    disabled: range <= 0,
  };
}

export function snapLoadBudgetValue(
  value: number,
  bounds: { min: number; max: number; step: number },
) {
  if (bounds.max <= bounds.min) return bounds.min;
  const clamped = Math.min(bounds.max, Math.max(bounds.min, value));
  const steps = Math.round((clamped - bounds.min) / bounds.step);
  return Math.min(bounds.max, bounds.min + steps * bounds.step);
}

export function clampLoadBudget(
  budget: GraphLoadBudget,
  totals: GraphCatalogTotals,
): GraphLoadBudget {
  const nodeCeiling = catalogNodeCeiling(totals);
  const edgeCeiling = catalogEdgeCeiling(totals);
  const minNodes = nodeCeiling === 0 ? 0 : Math.min(GRAPH_LOAD_BUDGET_MIN_NODES, nodeCeiling);
  const minEdges = edgeCeiling === 0 ? 0 : Math.min(GRAPH_LOAD_BUDGET_MIN_EDGES, edgeCeiling);

  return {
    maxNodes: nodeCeiling === 0
      ? 0
      : Math.min(Math.max(minNodes, Math.round(budget.maxNodes)), nodeCeiling),
    maxEdges: edgeCeiling === 0
      ? 0
      : Math.min(Math.max(minEdges, Math.round(budget.maxEdges)), edgeCeiling),
  };
}

export function defaultLoadBudget(totals: GraphCatalogTotals): GraphLoadBudget {
  const nodeCeiling = catalogNodeCeiling(totals);
  const edgeCeiling = catalogEdgeCeiling(totals);
  return clampLoadBudget(
    {
      maxNodes: nodeCeiling || DEFAULT_BUDGET_NODES,
      maxEdges: edgeCeiling || DEFAULT_BUDGET_EDGES,
    },
    totals,
  );
}

function largerTotal(sessionCount: number | null, catalogCount: number | null | undefined): number | null {
  if (sessionCount == null) return catalogCount ?? null;
  if (catalogCount == null) return sessionCount;
  return Math.max(sessionCount, catalogCount);
}

export function mergeCatalogTotals(
  stats: GraphCatalogTotals,
  fromLoad?: { graphNodeTotal?: number | null; graphEdgeTotal?: number | null } | null,
): GraphCatalogTotals {
  return {
    nodeTotal: largerTotal(stats.nodeTotal, fromLoad?.graphNodeTotal),
    edgeTotal: largerTotal(stats.edgeTotal, fromLoad?.graphEdgeTotal),
  };
}

/** When the canvas loaded the full graph (not truncated), keep the slider at the catalog ceiling. */
export function alignLoadBudgetWithLoaded(
  budget: GraphLoadBudget,
  totals: GraphCatalogTotals,
  loaded: { nodes: number; edges: number },
  loadTruncated: boolean,
): GraphLoadBudget {
  const clamped = clampLoadBudget(budget, totals);
  if (loadTruncated) {
    return clamped;
  }
  return clampLoadBudget(
    {
      maxNodes: Math.max(clamped.maxNodes, loaded.nodes),
      maxEdges: Math.max(clamped.maxEdges, loaded.edges),
    },
    totals,
  );
}
