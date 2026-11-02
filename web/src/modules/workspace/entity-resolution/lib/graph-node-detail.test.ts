import { describe, expect, it } from 'vitest';
import { diffGraphNodeFields, graphNodeFieldMap } from '@/modules/workspace/entity-resolution/lib/graph-node-detail.js';

describe('workspace-graph-node-detail', () => {
  it('diffGraphNodeFields marks differing keys', () => {
    const a = graphNodeFieldMap({
      id: 'n1',
      type: 'entity',
      content: 'Alice',
      properties: { country: 'US' },
    });
    const b = graphNodeFieldMap({
      id: 'n2',
      type: 'entity',
      content: 'Alice',
      properties: { country: 'UK' },
    });
    const rows = diffGraphNodeFields(a, b);
    const country = rows.find((r) => r.key === 'country');
    expect(country?.differs).toBe(true);
    expect(rows.find((r) => r.key === 'content')?.differs).toBe(false);
  });
});
