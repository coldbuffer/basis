import type { MDXComponents } from 'mdx/types';
import type { FC } from 'react';

import browserCollections from '@/.source/browser.js';

import { docsMdxComponents } from '@/components/app/marketing/docs/docs-mdx-components.js';
import type { Locale } from '@/i18n/context.js';
import { docsPath, type DocSlug } from '@/modules/public/docs/lib/product-docs-nav.js';
import { productDocsSource } from '@/modules/public/docs/lib/product-docs-source.js';

/** Fumadocs MDX client loader (Vite SPA). */
export const productDocsMdx = browserCollections.docs.createClientLoader({
  id: 'product-docs',
  component(loaded: { default: FC<{ components?: MDXComponents }> }) {
    const Content = loaded.default;
    return <Content components={docsMdxComponents} />;
  },
});

export function productDocsMdxPath(locale: Locale, slug: DocSlug): string {
  const url = docsPath(slug);
  const page = productDocsSource.getPageByUrl(url, locale);
  if (!page) {
    throw new Error(`Unknown docs page: ${url} (${locale})`);
  }
  // Fumadocs page paths are relative to `content/docs` and match the client loader keys.
  return page.path;
}
