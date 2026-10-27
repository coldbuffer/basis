import { describe, expect, it } from 'vitest';

import { searchProductDocs, type DocsSearchEntry } from '@/modules/docs/lib/product-docs-search.js';

const sample: DocsSearchEntry[] = [
  { slug: 'quickstart', url: '/docs/quickstart', title: 'Quickstart', description: 'Run locally' },
  { slug: 'mcp', url: '/docs/mcp', title: 'MCP for agents', description: 'HTTP MCP setup' },
  { slug: 'deployment', url: '/docs/deployment', title: 'Self-host', description: 'Docker compose' },
];

describe('searchProductDocs', () => {
  it('returns empty for blank query', () => {
    expect(searchProductDocs(sample, '')).toEqual([]);
  });

  it('matches title and ranks prefix higher', () => {
    const hits = searchProductDocs(sample, 'mcp');
    expect(hits[0]?.slug).toBe('mcp');
  });

  it('matches description', () => {
    const hits = searchProductDocs(sample, 'docker');
    expect(hits.some((h) => h.slug === 'deployment')).toBe(true);
  });
});
