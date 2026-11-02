import { describe, expect, it } from 'vitest';

import { entitiesStatementPath, parseEntitiesUrlState } from '@/modules/workspace/entities/lib/entities-url-state.js';

describe('entitiesUrlState', () => {
  it('parses statement deep link', () => {
    expect(parseEntitiesUrlState('?statement=stmt-1').statementId).toBe('stmt-1');
  });

  it('builds entities statement path', () => {
    expect(entitiesStatementPath('kb-1', 'stmt-9')).toBe('/workspaces/kb-1/entities?statement=stmt-9');
  });
});
