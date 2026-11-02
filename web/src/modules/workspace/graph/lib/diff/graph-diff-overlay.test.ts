import { describe, expect, it } from 'vitest';
import {
  graphDiffEdgeKey,
  graphDiffOverlayFromResponse,
  graphDiffEdgeTouchesChange,
} from '@/modules/workspace/graph/lib/diff/graph-diff-overlay.js';

describe('graphDiffOverlayFromResponse', () => {
  it('builds sets for added and modified nodes', () => {
    const overlay = graphDiffOverlayFromResponse(
      {
        added_nodes: ['a'],
        removed_nodes: ['b'],
        modified_nodes: [{ id: 'c' }],
        added_edges: [{ source_id: 's', target_id: 't', type: 'knows' }],
      },
      'a',
    );
    expect(overlay.enabled).toBe(true);
    expect(overlay.added.has('a')).toBe(true);
    expect(overlay.modified.has('c')).toBe(true);
    expect(overlay.focusNodeId).toBe('a');
    expect(overlay.addedEdgeKeys.has(graphDiffEdgeKey('s', 't', 'knows'))).toBe(true);
  });

  it('detects endpoint touch for edge emphasis', () => {
    const overlay = graphDiffOverlayFromResponse(
      { added_nodes: ['n1'], removed_nodes: [], modified_nodes: [], added_edges: [] },
      null,
    );
    expect(graphDiffEdgeTouchesChange('n1', 'x', overlay)).toBe(true);
    expect(graphDiffEdgeTouchesChange('a', 'b', overlay)).toBe(false);
  });
});
