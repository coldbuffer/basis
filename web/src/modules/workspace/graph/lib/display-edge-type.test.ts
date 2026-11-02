import { describe, expect, it } from 'vitest';
import { displayGraphEdgeType } from './display-edge-type.js';

describe('displayGraphEdgeType', () => {
  it('passes through ordinary types', () => {
    expect(displayGraphEdgeType('related_to', null)).toBe('related_to');
  });

  it('uses alignment_relation for vocabulary alignment edges', () => {
    expect(
      displayGraphEdgeType('vocabulary_alignment:abc', {
        alignment_relation: 'skos:exactMatch',
      }),
    ).toBe('skos:exactMatch');
  });

  it('falls back when relation metadata is missing', () => {
    expect(displayGraphEdgeType('vocabulary_alignment:abc', {})).toBe('vocabulary_alignment');
  });
});
