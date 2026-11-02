import { describe, expect, it } from 'vitest';

import { batchMergeEdges, batchMergeNodes, clearGraph } from '@/lib/workspace/graphStore.js';
import { resolveGraphNodeEvidenceLinks } from './graph-evidence-links.js';

describe('resolveGraphNodeEvidenceLinks', () => {
  const workspaceId = 'kb-1';

  it('links document nodes by id and type', () => {
    const links = resolveGraphNodeEvidenceLinks(workspaceId, 'snap-doc', 'document', {});
    expect(links.some((l) => l.kind === 'sources-doc' && l.to.includes('doc=snap-doc'))).toBe(true);
  });

  it('prefers chunk property over search fallback', () => {
    const links = resolveGraphNodeEvidenceLinks(workspaceId, 'node-1', 'Entity', {
      chunk_id: 'chunk-abc',
    });
    expect(links).toHaveLength(1);
    expect(links[0].kind).toBe('sources-chunk');
    expect(links[0].to).toContain('chunk=chunk-abc');
  });

  it('falls back to search when no evidence fields', () => {
    const links = resolveGraphNodeEvidenceLinks(workspaceId, 'opaque-id', 'Entity', {});
    expect(links).toHaveLength(1);
    expect(links[0].kind).toBe('search');
    expect(links[0].to).toContain('q=opaque-id');
  });

  it('uses chunk_id from graph edges when node properties are empty', () => {
    clearGraph();
    batchMergeNodes([
      { id: 'entity-1', attributes: { label: 'E', x: 0, y: 0, nodeType: 'entity', properties: {} } },
      { id: 'doc-1', attributes: { label: 'D', x: 1, y: 0, nodeType: 'document', properties: {} } },
    ]);
    batchMergeEdges([
      {
        id: 'e1',
        familyId: 'e1',
        source: 'entity-1',
        target: 'doc-1',
        attributes: {
          edgeId: 'e1',
          familyId: 'e1',
          sourceId: 'entity-1',
          targetId: 'doc-1',
          properties: { chunk_id: 'chunk-from-edge' },
        },
      },
    ]);

    const links = resolveGraphNodeEvidenceLinks(workspaceId, 'entity-1', 'entity', {});
    expect(links.some((l) => l.kind === 'sources-chunk' && l.to.includes('chunk-from-edge'))).toBe(
      true,
    );
    clearGraph();
  });
});
