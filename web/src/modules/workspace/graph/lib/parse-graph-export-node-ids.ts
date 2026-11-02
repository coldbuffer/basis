/** Parse comma- or newline-separated node ids for `POST …/export`. */

export function parseGraphExportNodeIds(raw: string): string[] {
  const parts = raw
    .split(/[\n,]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  return [...new Set(parts)];
}

export function formatGraphExportNodeIds(ids: string[]): string {
  return ids.join('\n');
}
