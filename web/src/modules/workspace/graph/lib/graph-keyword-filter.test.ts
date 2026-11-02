import { describe, expect, it } from "vitest";

import { isNodeKeywordSuppressed, nodeMatchesKeywordFilter, normalizeKeywordFilter } from "./graph-keyword-filter";

describe("graphKeywordFilter", () => {
  it("matches label, content, type, and id case-insensitively", () => {
    const attrs = { label: "Acme Corp", content: "", nodeType: "entity" };
    expect(nodeMatchesKeywordFilter(attrs, "node-1", normalizeKeywordFilter("acme"))).toBe(true);
    expect(nodeMatchesKeywordFilter(attrs, "node-1", normalizeKeywordFilter("entity"))).toBe(true);
    expect(nodeMatchesKeywordFilter(attrs, "uuid-abc", normalizeKeywordFilter("uuid"))).toBe(true);
    expect(nodeMatchesKeywordFilter(attrs, "node-1", normalizeKeywordFilter("missing"))).toBe(false);
  });

  it("suppresses only when a non-empty query fails to match", () => {
    const attrs = { label: "Doc", content: "hello", nodeType: "document" };
    expect(isNodeKeywordSuppressed(attrs, "n1", "")).toBe(false);
    expect(isNodeKeywordSuppressed(attrs, "n1", "hello")).toBe(false);
    expect(isNodeKeywordSuppressed(attrs, "n1", "zzz")).toBe(true);
  });
});
