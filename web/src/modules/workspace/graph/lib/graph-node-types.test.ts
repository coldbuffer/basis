import Graph from "graphology";
import { describe, expect, it } from "vitest";

import { collectNodeTypeCounts, isNodeTypeSuppressed, mergeNodeTypeCounts } from "./graph-node-types";

describe("collectNodeTypeCounts", () => {
  it("counts node types and keeps document before entity", () => {
    const graph = new Graph();
    graph.addNode("e1", { nodeType: "entity" });
    graph.addNode("e2", { nodeType: "entity" });
    graph.addNode("d1", { nodeType: "document" });
    graph.addNode("l1", { nodeType: "literal" });

    expect(collectNodeTypeCounts(graph)).toEqual([
      { type: "document", count: 1 },
      { type: "entity", count: 2 },
      { type: "literal", count: 1 },
    ]);
  });

  it("appends display-only types without replacing loaded counts", () => {
    const merged = mergeNodeTypeCounts(
      [{ type: "entity", count: 4 }],
      [{ type: "entity", count: 1 }, { type: "community", count: 2 }],
    );
    expect(merged).toEqual([
      { type: "entity", count: 4 },
      { type: "community", count: 2 },
    ]);
  });
});

describe("isNodeTypeSuppressed", () => {
  it("hides only types that are switched off", () => {
    const hidden = new Set(["document"]);
    expect(isNodeTypeSuppressed("document", hidden)).toBe(true);
    expect(isNodeTypeSuppressed("entity", hidden)).toBe(false);
    expect(isNodeTypeSuppressed(undefined, new Set())).toBe(false);
  });
});
