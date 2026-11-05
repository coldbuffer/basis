import { describe, expect, it } from 'vitest';
import {
  searchPath,
  parseSearchUrlState,
  resolveSearchScope,
  chunkTemporalFromUrlState,
} from '@/modules/workspace/search/lib/search-url-state.js';

describe('searchUrlState', () => {
  it('parses scope param', () => {
    const state = parseSearchUrlState('?scope=graph&q=smoke');
    expect(state.scope).toBe('graph');
    expect(state.q).toBe('smoke');

    expect(resolveSearchScope(null)).toBe('chunks');
    expect(resolveSearchScope('all')).toBe('chunks');
  });

  it('builds shareable search paths', () => {
    const href = searchPath('kb-1', { scope: 'graph', q: 'node' });
    expect(href).toBe('/workspaces/kb-1/search?scope=graph&q=node');
  });

  it('round-trips temporal query params', () => {
    const href = searchPath('kb-1', {
      scope: 'chunks',
      q: 'x',
      createdAfter: '2030-01-01T00:00:00.000Z',
      createdBefore: '2030-01-31T23:59:59.999Z',
      at: '2030-06-01T00:00:00Z',
    });
    const parsed = parseSearchUrlState(href.split('?')[1] ?? '');
    expect(parsed.createdAfter).toBe('2030-01-01T00:00:00.000Z');
    expect(parsed.createdBefore).toBe('2030-01-31T23:59:59.999Z');
    expect(parsed.at).toBe('2030-06-01T00:00:00Z');
  });

  it('maps legacy as_of to createdBefore', () => {
    const parsed = parseSearchUrlState('?as_of=2030-01-01T00:00:00Z');
    expect(parsed.createdBefore).toBe('2030-01-01T00:00:00Z');
    expect(chunkTemporalFromUrlState(parsed).createdBefore).toBe('2030-01-01T00:00:00Z');
  });
});
