import { describe, expect, it } from 'vitest';
import { reviewItemQualityHref, reviewItemQualityLinkLabelKey } from './review-quality-link.js';

describe('reviewItemQualityHref', () => {
  const ws = 'ws-1';

  it('links hub SHACL to structure tab with ontology', () => {
    const href = reviewItemQualityHref(ws, 'shacl_violation', {
      detector: 'l3_hub_shacl',
      ontology_uri: 'http://ex/onto',
    });
    expect(href).toBe('/workspaces/ws-1/quality?tab=structure&ontology_uri=http%3A%2F%2Fex%2Fonto');
  });

  it('links L2 SHACL to mappings', () => {
    expect(reviewItemQualityHref(ws, 'shacl_violation', { detector: 'l2_shacl_max_count' })).toBe(
      '/workspaces/ws-1/mappings',
    );
  });

  it('links low confidence to mappings', () => {
    expect(reviewItemQualityHref(ws, 'low_confidence', {})).toBe('/workspaces/ws-1/mappings');
  });
});

describe('reviewItemQualityLinkLabelKey', () => {
  it('picks label by detector', () => {
    expect(
      reviewItemQualityLinkLabelKey('shacl_violation', { detector: 'l3_hub_shacl' }),
    ).toBe('open_data_quality_structure');
    expect(
      reviewItemQualityLinkLabelKey('shacl_violation', { detector: 'l2_shacl_max_count' }),
    ).toBe('open_statement_mappings');
  });
});
