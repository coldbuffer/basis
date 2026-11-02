import { describe, expect, it } from 'vitest';
import { statementTypeMappingHref } from './statement-type-mapping-link.js';

describe('statementTypeMappingHref', () => {
  it('includes tab and label query params', () => {
    const href = statementTypeMappingHref('ws-1', { label: '人' });
    expect(href).toContain('/workspaces/ws-1/ontology');
    expect(href).toContain('tab=statement');
    expect(href).toContain('typeMappingLabel');
  });

  it('adds target URI when provided', () => {
    const href = statementTypeMappingHref('ws-1', {
      label: 'Person',
      targetUri: 'http://example.org/Person',
    });
    expect(href).toContain('typeMappingUri=http');
  });
});
