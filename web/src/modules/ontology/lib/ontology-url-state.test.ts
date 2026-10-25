import { describe, expect, it } from 'vitest';

import { applyTab, parseOntologyUrlState } from '@/modules/ontology/lib/ontology-url-state.js';

describe('ontologyUrlState', () => {
  it('reads proposal deep link via tab param', () => {
    const state = parseOntologyUrlState(
      '?tab=versions&ontologyProposal=prop-abc&ontologyEntity=http%3A%2F%2Fex',
    );
    expect(state.tab).toBe('versions');
    expect(state.proposalId).toBe('prop-abc');
    expect(state.entityUri).toBe('http://ex');
  });

  it('writes canonical tab param', () => {
    expect(applyTab('?foo=1', 'editor')).toBe('?foo=1&tab=editor');
    expect(applyTab('?tab=editor&foo=1', 'registry')).toBe('?foo=1');
  });
});
