import { describe, expect, it } from "vitest";

import { compareVersionIds, sortVersionsNewestFirst } from "./version-sort.js";

describe("version-sort", () => {
  it("orders semver newest first", () => {
    const sorted = sortVersionsNewestFirst([
      { version_id: "1.1.0" },
      { version_id: "1.5.0" },
      { version_id: "1.2.0" },
    ]);
    expect(sorted.map((r) => r.version_id)).toEqual(["1.5.0", "1.2.0", "1.1.0"]);
  });

  it("compareVersionIds handles equal", () => {
    expect(compareVersionIds("1.0.0", "1.0.0")).toBe(0);
  });
});
