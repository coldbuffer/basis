import { findNeighbour } from 'fumadocs-core/page-tree';

import type { Locale } from '@/i18n/context.js';
import { docsPath, type DocSlug } from '@/modules/public/docs/lib/product-docs-nav.js';
import { productDocsPageTree } from '@/modules/public/docs/lib/product-docs-source.js';

export type DocsAdjacentPage = {
  name: string;
  href: string;
};

export function productDocsNeighbours(
  locale: Locale,
  slug: DocSlug,
): { previous?: DocsAdjacentPage; next?: DocsAdjacentPage } {
  const tree = productDocsPageTree(locale);
  const { previous, next } = findNeighbour(tree, docsPath(slug));
  return {
    previous: previous
      ? { name: String(previous.name), href: previous.url }
      : undefined,
    next: next ? { name: String(next.name), href: next.url } : undefined,
  };
}
