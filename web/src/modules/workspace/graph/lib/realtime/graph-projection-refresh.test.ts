import { describe, expect, it } from "vitest";
import { shouldApplyProjectionRevision } from "./graph-projection-refresh.js";

describe("shouldApplyProjectionRevision", () => {
  it("applies when no prior revision is tracked", () => {
    expect(shouldApplyProjectionRevision(null, 1)).toBe(true);
    expect(shouldApplyProjectionRevision(null, undefined)).toBe(true);
  });

  it("skips duplicate or older revisions", () => {
    expect(shouldApplyProjectionRevision(5, 5)).toBe(false);
    expect(shouldApplyProjectionRevision(5, 3)).toBe(false);
  });

  it("applies strictly newer revisions", () => {
    expect(shouldApplyProjectionRevision(5, 6)).toBe(true);
  });
});
