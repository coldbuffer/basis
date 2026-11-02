import { describe, expect, it } from 'vitest';

import { formatGraphExportNodeIds, parseGraphExportNodeIds } from './parse-graph-export-node-ids.js';

describe('parseGraphExportNodeIds', () => {
  it('splits on commas and newlines and dedupes', () => {
    expect(parseGraphExportNodeIds('a, b\nb\nc')).toEqual(['a', 'b', 'c']);
  });

  it('formats ids one per line', () => {
    expect(formatGraphExportNodeIds(['x', 'y'])).toBe('x\ny');
  });
});
