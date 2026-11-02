/** Sort ontology version ids (semver when possible). */

export function versionSortKey(versionId: string): number[] | string[] {
  const text = versionId.trim();
  const parts = text.split(".");
  const numeric = parts.map((p) => Number.parseInt(p, 10));
  if (numeric.every((n) => !Number.isNaN(n))) {
    return numeric;
  }
  return [text];
}

export function compareVersionIds(a: string, b: string): number {
  const ka = versionSortKey(a);
  const kb = versionSortKey(b);
  const len = Math.max(ka.length, kb.length);
  for (let i = 0; i < len; i += 1) {
    const va = ka[i] ?? 0;
    const vb = kb[i] ?? 0;
    if (va < vb) return -1;
    if (va > vb) return 1;
  }
  return 0;
}

export function sortVersionsNewestFirst<T extends { version_id: string }>(rows: T[]): T[] {
  return [...rows].sort((left, right) =>
    compareVersionIds(right.version_id, left.version_id),
  );
}
