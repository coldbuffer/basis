import { describe, expect, it } from 'vitest';
import {
  clearGraphDiffPreviewParams,
  graphDiffPreviewPath,
  graphImportDialogPath,
  graphPath,
  mergeGraphAtParam,
  parseGraphDiffPreviewParams,
  parseGraphUrlState,
} from '@/modules/workspace/graph/lib/graph-url-state.js';

describe('graphUrlState', () => {
  it('builds focus + at links', () => {
    expect(graphPath('kb-1', { focus: 'n1', at: '2026-01-01' })).toBe(
      '/workspaces/kb-1/graph?focus=n1&at=2026-01-01',
    );
  });

  it('builds timeline entry links', () => {
    expect(graphPath('kb-1', { timeline: true })).toBe('/workspaces/kb-1/graph?timeline=1');
    expect(parseGraphUrlState('?timeline=1').timeline).toBe(true);
  });

  it('parses at from query', () => {
    expect(parseGraphUrlState('?focus=a&at=2030-01-01T00:00:00Z').at).toBe('2030-01-01T00:00:00Z');
  });

  it('builds import dialog deep links', () => {
    expect(graphImportDialogPath('kb-1')).toBe('/workspaces/kb-1/graph?import=1');
  });

  it('builds diff preview canvas links', () => {
    expect(graphDiffPreviewPath('kb-1', '2020-01-01', '2021-01-01')).toBe(
      '/workspaces/kb-1/graph?at=2021-01-01&diff_from=2020-01-01&diff_to=2021-01-01',
    );
    expect(
      parseGraphDiffPreviewParams('?diff_from=a&diff_to=b&at=b')?.diffFrom,
    ).toBe('a');
    const cleared = clearGraphDiffPreviewParams('focus=n&diff_from=a&diff_to=b');
    expect(cleared.get('focus')).toBe('n');
    expect(cleared.has('diff_from')).toBe(false);
  });

  it('merges at while preserving focus', () => {
    const next = mergeGraphAtParam('focus=node-1', '2030-06-01T00:00:00Z');
    expect(next.get('focus')).toBe('node-1');
    expect(next.get('at')).toBe('2030-06-01T00:00:00Z');
  });
});
