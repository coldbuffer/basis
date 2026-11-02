import type { GraphDiffFocusResponse } from '@/modules/workspace/graph/lib/diff/graph-diff-focus.js';

export type GraphDiffMergePick = {
  primary: string;
  duplicate: string;
};

export type GraphDiffMergePickSlot = 'primary' | 'duplicate';

export function emptyGraphDiffMergePick(): GraphDiffMergePick {
  return { primary: '', duplicate: '' };
}

/** Nodes visible on the end-instant canvas that may be merge targets. */
export function isGraphDiffMergeCandidate(
  nodeId: string,
  diff: GraphDiffFocusResponse,
): boolean {
  const id = nodeId.trim();
  if (!id) return false;
  if (diff.added_nodes.includes(id)) return true;
  return diff.modified_nodes.some((row) => row.id === id);
}

export function applyGraphDiffMergePick(
  pick: GraphDiffMergePick,
  nodeId: string,
  slot: GraphDiffMergePickSlot,
): { pick: GraphDiffMergePick; nextSlot: GraphDiffMergePickSlot } {
  const id = nodeId.trim();
  const next =
    slot === 'primary'
      ? { ...pick, primary: id }
      : { ...pick, duplicate: id };
  return {
    pick: next,
    nextSlot: slot === 'primary' ? 'duplicate' : 'primary',
  };
}

export function graphDiffMergePickReady(pick: GraphDiffMergePick): boolean {
  const primary = pick.primary.trim();
  const duplicate = pick.duplicate.trim();
  return Boolean(primary && duplicate && primary !== duplicate);
}
