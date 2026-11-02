export function parseInstantMs(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const ms = Date.parse(trimmed);
  return Number.isNaN(ms) ? null : ms;
}

export function clampMs(value: number, minMs: number, maxMs: number): number {
  return Math.min(maxMs, Math.max(minMs, value));
}

export function msToIso(ms: number): string {
  return new Date(ms).toISOString();
}
