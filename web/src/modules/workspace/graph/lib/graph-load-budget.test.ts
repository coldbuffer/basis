import { describe, expect, it } from "vitest";

import {
  alignLoadBudgetWithLoaded,
  clampLoadBudget,
  defaultLoadBudget,
  loadBudgetSliderBounds,
  mergeCatalogTotals,
} from "./graph-load-budget";

describe("mergeCatalogTotals", () => {
  it("keeps the full catalog total when the live session is only the loaded slice", () => {
    expect(mergeCatalogTotals(
      { nodeTotal: 200, edgeTotal: 400 },
      { graphNodeTotal: 4800, graphEdgeTotal: 12000 },
    )).toEqual({
      nodeTotal: 4800,
      edgeTotal: 12000,
    });
  });

  it("uses the session count when the catalog total is still unknown", () => {
    expect(mergeCatalogTotals(
      { nodeTotal: 200, edgeTotal: null },
      { graphNodeTotal: null, graphEdgeTotal: null },
    )).toEqual({
      nodeTotal: 200,
      edgeTotal: null,
    });
  });
});

describe("alignLoadBudgetWithLoaded", () => {
  it("raises the stored budget to the loaded totals when the graph was not truncated", () => {
    const totals = { nodeTotal: 4800, edgeTotal: 12000 };
    expect(alignLoadBudgetWithLoaded(
      { maxNodes: 20, maxEdges: 20 },
      totals,
      { nodes: 4800, edges: 12000 },
      false,
    )).toEqual({ maxNodes: 4800, maxEdges: 12000 });
  });

  it("keeps a lower budget when the graph load was truncated", () => {
    const totals = { nodeTotal: 4800, edgeTotal: 12000 };
    expect(alignLoadBudgetWithLoaded(
      { maxNodes: 200, maxEdges: 400 },
      totals,
      { nodes: 200, edges: 400 },
      true,
    )).toEqual({ maxNodes: 200, maxEdges: 400 });
  });
});

describe("defaultLoadBudget", () => {
  it("uses the full catalog ceiling when totals are known", () => {
    expect(defaultLoadBudget({ nodeTotal: 434, edgeTotal: 800 })).toEqual({
      maxNodes: 434,
      maxEdges: 800,
    });
  });
});

describe("clampLoadBudget", () => {
  it("does not enforce a 20-node minimum", () => {
    const budget = clampLoadBudget({ maxNodes: 8, maxEdges: 12 }, { nodeTotal: 8, edgeTotal: 12 });
    expect(budget).toEqual({ maxNodes: 8, maxEdges: 12 });
    expect(loadBudgetSliderBounds(8, 1)).toEqual({
      min: 1,
      max: 8,
      step: 1,
      disabled: false,
    });
    expect(loadBudgetSliderBounds(60, 1)).toEqual({
      min: 1,
      max: 60,
      step: 1,
      disabled: false,
    });
  });
});
