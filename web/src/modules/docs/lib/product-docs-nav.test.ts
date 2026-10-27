import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { DOC_SLUGS, docsPath } from '@/modules/docs/lib/product-docs-nav.js';

const contentRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '../../../../content/docs',
);

/** Slugs derived from the actual docs files (Fumadocs route slugs). */
function contentSlugs(locale: string): Set<string> {
  return new Set(
    fs
      .readdirSync(path.join(contentRoot, locale))
      .filter((name) => /\.(md|mdx)$/.test(name))
      .map((name) => name.replace(/\.(md|mdx)$/, ''))
      .map((slug) => (slug === 'index' ? 'overview' : slug)),
  );
}

/** Slugs listed in the Fumadocs sidebar meta (`---Group---` entries are separators). */
function metaPageSlugs(locale: string): Set<string> {
  const metaPath = path.join(contentRoot, locale, 'meta.json');
  const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8')) as { pages?: string[] };
  return new Set(
    (meta.pages ?? [])
      .filter((page) => !/^---.*---$/.test(page))
      .map((page) => (page === 'index' ? 'overview' : page)),
  );
}

describe('product docs slugs', () => {
  it.each(['en', 'zh'])('covers every page under content/docs/%s', (locale) => {
    expect(new Set(DOC_SLUGS)).toEqual(contentSlugs(locale));
  });

  it.each(['en', 'zh'])('lists every page in content/docs/%s/meta.json', (locale) => {
    expect(metaPageSlugs(locale)).toEqual(contentSlugs(locale));
  });

  it('maps overview and additional pages to their docs paths', () => {
    expect(docsPath('overview')).toBe('/docs');
    expect(docsPath('connectors-basis')).toBe('/docs/connectors-basis');
    expect(docsPath('bocp')).toBe('/docs/bocp');
    expect(docsPath('bocp-guide')).toBe('/docs/bocp-guide');
    expect(docsPath('console-tour')).toBe('/docs/console-tour');
  });
});
