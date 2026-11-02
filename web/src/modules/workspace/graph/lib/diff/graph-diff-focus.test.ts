import { describe, expect, it } from 'vitest';
import { diffFocusEntries, nextDiffFocusIndex } from '@/modules/workspace/graph/lib/diff/graph-diff-focus.js';

describe('diffFocusEntries', () => {
  it('orders added, removed, then modified', () => {
    const entries = diffFocusEntries({
      added_nodes: ['a'],
      removed_nodes: ['b'],
      modified_nodes: [{ id: 'c' }],
    });
    expect(entries.map((e) => e.nodeId)).toEqual(['a', 'b', 'c']);
  });
});

describe('nextDiffFocusIndex', () => {
  it('wraps around', () => {
    expect(nextDiffFocusIndex(2, 1, 3)).toBe(0);
    expect(nextDiffFocusIndex(0, -1, 3)).toBe(2);
  });
});
