import { describe, expect, it } from 'vitest';

import {
  authCredentialFieldsAreBlank,
  authFieldValuesFromObject,
} from '@/modules/workspace/connectors/lib/connector-auth-fields.js';

describe('authFieldValuesFromObject', () => {
  it('merges saved connection_config into field values', () => {
    const fields = [
      { key: 'host', label: 'Host' },
      { key: 'port', label: 'Port', input_type: 'number' },
    ];
    expect(
      authFieldValuesFromObject(fields, { host: 'db.internal', port: 5433 }),
    ).toEqual({ host: 'db.internal', port: '5433' });
  });
});

describe('authCredentialFieldsAreBlank', () => {
  it('returns true when all credential inputs are empty', () => {
    const fields = [{ key: 'password', label: 'Password', secret: true }];
    expect(authCredentialFieldsAreBlank(fields, { password: '' })).toBe(true);
    expect(authCredentialFieldsAreBlank(fields, { password: 'x' })).toBe(false);
  });
});
