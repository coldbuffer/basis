import Graph from "graphology";
import { describe, expect, it } from "vitest";

import { collectEdgeTypeCounts, isEdgeTypeSuppressed, mergeEdgeTypeCounts } from "./graph-edge-types";

describe("collectEdgeTypeCounts", () => {
  it("counts edge types with the most common type first", () => {
    const graph = new Graph({ multi: true });
    graph.addNode("a");
    graph.addNode("b");
    graph.addNode("c");
    graph.addEdge("a", "b", { edgeType: "related_to" });
    graph.addEdge("b", "c", { edgeType: "related_to" });
    graph.addEdge("a", "c", { edgeType: "mentions" });

    expect(collectEdgeTypeCounts(graph)).toEqual([
      { type: "related_to", count: 2 },
      { type: "mentions", count: 1 },
    ]);
  });

  it("appends display-only types without replacing loaded counts", () => {
    expect(
      mergeEdgeTypeCounts(
        [{ type: "related_to", count: 4 }],
        [{ type: "related_to", count: 1 }, { type: "part_of", count: 2 }],
      ),
    ).toEqual([
      { type: "related_to", count: 4 },
      { type: "part_of", count: 2 },
    ]);
  });
});

describe("isEdgeTypeSuppressed", () => {
  it("hides only types that are switched off", () => {
    const hidden = new Set(["mentions"]);
    expect(isEdgeTypeSuppressed("mentions", hidden)).toBe(true);
    expect(isEdgeTypeSuppressed("related_to", hidden)).toBe(false);
    expect(isEdgeTypeSuppressed(undefined, new Set())).toBe(false);
  });
});
