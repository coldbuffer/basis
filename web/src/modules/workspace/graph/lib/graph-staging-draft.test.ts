import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearGraphStagingDraft,
  readGraphStagingDraft,
  writeGraphStagingDraft,
} from '@/modules/workspace/graph/lib/graph-staging-draft.js';

function mockWebStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => {
      map.delete(key);
    },
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
  };
}

describe('graph-staging-draft', () => {
  beforeEach(() => {
    vi.stubGlobal('sessionStorage', mockWebStorage());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    clearGraphStagingDraft('sess-1');
  });

  it('round-trips merge pick in sessionStorage', () => {
    writeGraphStagingDraft('sess-1', { primary: 'a', duplicate: 'b' });
    expect(readGraphStagingDraft('sess-1')).toEqual({ primary: 'a', duplicate: 'b' });
    clearGraphStagingDraft('sess-1');
    expect(readGraphStagingDraft('sess-1')).toBeNull();
  });
});
