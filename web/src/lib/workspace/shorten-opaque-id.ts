/** Compact display for UUID-like ids when no label is available. */
export function shortenOpaqueId(id: string): string {
  const trimmed = id.trim();
  if (!trimmed) return trimmed;
  if (trimmed.length > 14 && /^[0-9a-f-]{36}$/i.test(trimmed)) {
    return `${trimmed.slice(0, 8)}…${trimmed.slice(-4)}`;
  }
  if (trimmed.length > 20) {
    return `${trimmed.slice(0, 10)}…${trimmed.slice(-4)}`;
  }
  return trimmed;
}
