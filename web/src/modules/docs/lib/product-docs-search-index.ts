import type { Locale } from '@/i18n/context.js';
import { productDocsBodyTextBySlug } from '@/modules/docs/lib/product-docs-content-text.js';
import { DOC_SLUGS, docsPath } from '@/modules/docs/lib/product-docs-nav.js';
import { productDocsPageMeta } from '@/modules/docs/lib/product-docs-page-meta.js';

import type { DocsSearchEntry } from '@/modules/docs/lib/product-docs-search.js';

export type { DocsSearchEntry } from '@/modules/docs/lib/product-docs-search.js';
export { searchProductDocs } from '@/modules/docs/lib/product-docs-search.js';

export function productDocsSearchEntries(locale: Locale): DocsSearchEntry[] {
  const bodyBySlug = productDocsBodyTextBySlug(locale);
  const entries: DocsSearchEntry[] = [];
  for (const slug of DOC_SLUGS) {
    const meta = productDocsPageMeta(locale, slug);
    if (!meta) continue;
    entries.push({
      slug,
      url: docsPath(slug),
      title: meta.title,
      description: meta.description ?? '',
      bodyText: bodyBySlug[slug],
    });
  }
  return entries;
}
