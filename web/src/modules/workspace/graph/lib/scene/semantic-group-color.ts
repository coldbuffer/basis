const SEMANTIC_HUE_ORIGIN = 212;
const SEMANTIC_SATURATION = 50;
const SEMANTIC_LIGHTNESS = 48;

function hslToHex(hue: number, saturation: number, lightness: number): string {
  const normalizedHue = ((hue % 360) + 360) % 360;
  const s = saturation / 100;
  const l = lightness / 100;
  const chroma = s * Math.min(l, 1 - l);
  const channel = (offset: number) => {
    const k = (offset + normalizedHue / 30) % 12;
    const value = l - chroma * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * value)
      .toString(16)
      .padStart(2, "0");
  };
  return `#${channel(0)}${channel(8)}${channel(4)}`;
}

/** Evenly spaced hue so co-visible groups stay apart. Index 0 is stable blue. */
export function colorForSemanticGroupIndex(index: number, count: number): string {
  const safeCount = Math.max(count, 1);
  const hue = SEMANTIC_HUE_ORIGIN + (index * 360) / safeCount;
  return hslToHex(hue, SEMANTIC_SATURATION, SEMANTIC_LIGHTNESS);
}

/**
 * One color per semantic group. The same group name always maps to the same
 * color for a given set of groups, and different groups never share a color.
 */
export function assignSemanticGroupColors(groups: Iterable<string>): Map<string, string> {
  const unique = [...new Set(groups)].sort((left, right) => left.localeCompare(right));
  return new Map(
    unique.map((group, index) => [group, colorForSemanticGroupIndex(index, unique.length)]),
  );
}
