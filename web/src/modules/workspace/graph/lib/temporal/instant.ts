const ISO_WITHOUT_TZ_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

export function parseInstantMs(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const normalized = ISO_WITHOUT_TZ_RE.test(trimmed) ? `${trimmed}Z` : trimmed;
  const ms = Date.parse(normalized);
  return Number.isNaN(ms) ? null : ms;
}

export function clampMs(value: number, minMs: number, maxMs: number): number {
  return Math.min(maxMs, Math.max(minMs, value));
}

export function msToIso(ms: number): string {
  return new Date(ms).toISOString();
}
