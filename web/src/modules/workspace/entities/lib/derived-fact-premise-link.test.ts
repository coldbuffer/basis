import { describe, expect, it } from 'vitest';

import { hrefForDerivedFactPremise } from '@/modules/workspace/entities/lib/derived-fact-premise-link.js';

describe('hrefForDerivedFactPremise', () => {
  const entityId = '54d4f41b-3deb-4637-99ee-5d2bb081a4f5';
  const statementId = 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee';

  it('links entity uuid premises to graph focus', () => {
    expect(
      hrefForDerivedFactPremise('kb-1', { premise_kind: 'ground_fact', premise_id: entityId }),
    ).toBe(`/workspaces/kb-1/graph?focus=${encodeURIComponent(entityId)}`);
  });

  it('links statement uuid premises to entities statement deep link', () => {
    expect(
      hrefForDerivedFactPremise('kb-1', { premise_kind: 'statement', premise_id: statementId }),
    ).toBe(`/workspaces/kb-1/entities?statement=${encodeURIComponent(statementId)}`);
  });

  it('returns null for free-text premises', () => {
    expect(
      hrefForDerivedFactPremise('kb-1', {
        premise_kind: 'ground_fact',
        premise_id: 'parent(Alice, Bob)',
      }),
    ).toBeNull();
  });
});
