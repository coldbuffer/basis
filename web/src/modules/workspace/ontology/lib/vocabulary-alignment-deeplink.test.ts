import { describe, expect, it } from 'vitest';

import {
  applyVocabularyAlignmentSuggestParams,
  vocabularyAlignmentSuggestHref,
} from './vocabulary-alignment-deeplink.js';

describe('vocabularyAlignmentSuggestHref', () => {
  it('opens alignments tab with suggest flag', () => {
    const href = vocabularyAlignmentSuggestHref('ws-1');
    expect(href).toContain('/workspaces/ws-1/ontology');
    expect(href).toContain('tab=alignments');
    expect(href).toContain('alignSuggest=1');
    expect(href).not.toContain('alignOntology');
  });

  it('includes ontology context when provided', () => {
    const href = vocabularyAlignmentSuggestHref('ws-1', 'http://example.org/onto');
    expect(href).toContain('alignOntology=http');
  });
});

describe('applyVocabularyAlignmentSuggestParams', () => {
  it('preserves unrelated params', () => {
    const params = new URLSearchParams('foo=bar');
    applyVocabularyAlignmentSuggestParams(params, 'http://ex/o');
    expect(params.get('foo')).toBe('bar');
    expect(params.get('tab')).toBe('alignments');
    expect(params.get('alignSuggest')).toBe('1');
    expect(params.get('alignOntology')).toBe('http://ex/o');
  });
});
