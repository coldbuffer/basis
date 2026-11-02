import { describe, expect, it } from 'vitest';
import {
  applyGraphDiffMergePick,
  graphDiffMergePickReady,
  isGraphDiffMergeCandidate,
} from '@/modules/workspace/graph/lib/diff/graph-diff-merge-pick.js';

describe('graph-diff-merge-pick', () => {
  const diff = {
    added_nodes: ['a'],
    removed_nodes: ['z'],
    modified_nodes: [{ id: 'm' }],
  };

  it('accepts added and modified nodes only', () => {
    expect(isGraphDiffMergeCandidate('a', diff)).toBe(true);
    expect(isGraphDiffMergeCandidate('m', diff)).toBe(true);
    expect(isGraphDiffMergeCandidate('z', diff)).toBe(false);
  });

  it('fills slots and alternates pick target', () => {
    const first = applyGraphDiffMergePick({ primary: '', duplicate: '' }, 'a', 'primary');
    expect(first.pick.primary).toBe('a');
    expect(first.nextSlot).toBe('duplicate');
    const second = applyGraphDiffMergePick(first.pick, 'm', 'duplicate');
    expect(second.pick.duplicate).toBe('m');
    expect(graphDiffMergePickReady(second.pick)).toBe(true);
  });
});
