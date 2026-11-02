export type GraphDiffFocusResponse = {
  added_nodes: string[];
  removed_nodes: string[];
  modified_nodes: Array<{ id: string; change?: string }>;
};

export type DiffFocusEntry = {
  nodeId: string;
  change: 'added' | 'removed' | 'modified';
};

export function diffFocusEntries(diff: GraphDiffFocusResponse): DiffFocusEntry[] {
  const entries: DiffFocusEntry[] = [];
  for (const nodeId of diff.added_nodes) {
    entries.push({ nodeId, change: 'added' });
  }
  for (const nodeId of diff.removed_nodes) {
    entries.push({ nodeId, change: 'removed' });
  }
  for (const row of diff.modified_nodes) {
    entries.push({ nodeId: row.id, change: 'modified' });
  }
  return entries;
}

export function nextDiffFocusIndex(current: number, delta: number, length: number): number {
  if (length <= 0) return 0;
  return (current + delta + length) % length;
}
