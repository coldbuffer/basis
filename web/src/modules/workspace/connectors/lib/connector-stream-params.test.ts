import { describe, expect, it } from 'vitest';

import { extractStreamParamKeysFromStream } from '@/modules/workspace/connectors/lib/connector-stream-params.js';

describe('extractStreamParamKeysFromStream', () => {
  it('finds config placeholders in retriever path and mutations', () => {
    const keys = extractStreamParamKeysFromStream({
      name: 'issues',
      retriever: {
        path: '/repos/{{config.owner}}/{{config.repo}}/issues',
      },
      mutations: {
        update: {
          path_template: '/repos/{{config.owner}}/{{config.repo}}/issues/{{external_id}}',
        },
      },
    });
    expect(keys).toEqual(['owner', 'repo']);
  });

  it('ignores reserved template variables', () => {
    const keys = extractStreamParamKeysFromStream({
      retriever: { path: '/items/{{external_id}}' },
    });
    expect(keys).toEqual([]);
  });
});
