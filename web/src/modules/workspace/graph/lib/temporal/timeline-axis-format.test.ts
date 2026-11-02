import { describe, expect, it } from "vitest";
import { buildTimelineAxisFormat } from "./timeline-axis-format.js";

describe("buildTimelineAxisFormat", () => {
  it("localizes major month labels for zh", () => {
    const format = buildTimelineAxisFormat("zh");
    const label = format.majorLabels!(
      new Date(2024, 5, 15),
      "day",
      1,
    );
    expect(label).toMatch(/2024/);
    expect(label).not.toMatch(/June/);
  });

  it("hides week minor label on month boundary like vis-timeline", () => {
    const format = buildTimelineAxisFormat("en");
    const saturdayFirst = new Date(2023, 6, 1);
    expect(saturdayFirst.getDay()).not.toBe(0);
    const hidden = format.minorLabels!(saturdayFirst, "week", 1);
    expect(hidden).toBe("");
  });
});
