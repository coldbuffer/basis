import { describe, expect, it } from "vitest";

import { assignSemanticGroupColors } from "./semantic-group-color";

function hexHue(color: string): number {
  const red = Number.parseInt(color.slice(1, 3), 16) / 255;
  const green = Number.parseInt(color.slice(3, 5), 16) / 255;
  const blue = Number.parseInt(color.slice(5, 7), 16) / 255;
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const delta = max - min;
  if (delta === 0) return 0;
  const hue = max === red
    ? ((green - blue) / delta) % 6
    : max === green
      ? (blue - red) / delta + 2
      : (red - green) / delta + 4;
  return (hue * 60 + 360) % 360;
}

function hueDistance(left: number, right: number): number {
  const delta = Math.abs(left - right) % 360;
  return Math.min(delta, 360 - delta);
}

describe("assignSemanticGroupColors", () => {
  it("gives every node in a group the same color and keeps groups apart", () => {
    const colors = assignSemanticGroupColors(["person", "org", "person", "place", "org"]);

    expect(colors.size).toBe(3);
    expect(new Set(colors.values()).size).toBe(3);

    const hues = [...colors.values()].map(hexHue);
    const nearest = hues.flatMap((hue, index) => hues.slice(index + 1).map((other) => hueDistance(hue, other)));
    expect(Math.min(...nearest)).toBeGreaterThan(100);
  });

  it("stays stable for the same group set", () => {
    const first = assignSemanticGroupColors(["b", "a", "c"]);
    const second = assignSemanticGroupColors(["c", "b", "a"]);
    expect([...second.entries()]).toEqual([...first.entries()]);
  });
});
