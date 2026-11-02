import { describe, expect, it } from 'vitest';

import {
  parsePlatformAllowlistCsv,
  parsePlatformAllowlistJson,
} from '@/modules/admin/connectors/lib/platform-connector-allowlist-import.js';

describe('parsePlatformAllowlistCsv', () => {
  it('parses service + enabled columns', () => {
    const csv = `service,platform_enabled_draft
postgres,true
github,1
airtable,false
`;
    expect(parsePlatformAllowlistCsv(csv)).toEqual(['postgres', 'github']);
  });

  it('parses one service per line', () => {
    expect(parsePlatformAllowlistCsv('postgres\ngithub\n')).toEqual(['postgres', 'github']);
  });
});

describe('parsePlatformAllowlistJson', () => {
  it('parses allowed_providers array', () => {
    expect(
      parsePlatformAllowlistJson(JSON.stringify({ allowed_providers: ['postgres', 'github'] })),
    ).toEqual(['postgres', 'github']);
  });
});
