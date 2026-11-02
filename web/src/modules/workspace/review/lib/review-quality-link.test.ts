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

  it('links L2 SHACL to semantic alignment tab', () => {
    expect(reviewItemQualityHref(ws, 'shacl_violation', { detector: 'l2_shacl_max_count' })).toBe(
      '/workspaces/ws-1/ontology?tab=statement',
    );
  });

  it('links low confidence to semantic alignment tab', () => {
    expect(reviewItemQualityHref(ws, 'low_confidence', {})).toBe(
      '/workspaces/ws-1/ontology?tab=statement',
    );
  });

  it('links vocabulary alignment proposals to alignments tab', () => {
    const href = reviewItemQualityHref(ws, 'vocabulary_alignment_change', {
      action: 'upsert',
      source_uri: 'http://ex/a#Person',
      target_uri: 'http://ex/b#Human',
      relation: 'skos:exactMatch',
    });
    expect(href).toBe('/workspaces/ws-1/ontology?alignOntology=http%3A%2F%2Fex%2Fa&tab=alignments');
  });

  it('links unmapped type labels to prefilled create dialog', () => {
    const href = reviewItemQualityHref(ws, 'unmapped_entity_type', {
      label: '人',
      vocabulary_alignment_suggestions: [{ uri: 'http://ex/Person' }],
    });
    expect(href).toContain('tab=statement');
    expect(href).toContain('typeMappingLabel');
    expect(href).toContain('typeMappingUri');
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
    expect(reviewItemQualityLinkLabelKey('unmapped_entity_type', { label: '人' })).toBe(
      'open_create_type_mapping',
    );
    expect(reviewItemQualityLinkLabelKey('vocabulary_alignment_change', {})).toBe(
      'open_vocabulary_alignments',
    );
  });
});
