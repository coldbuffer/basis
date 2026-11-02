import type { Locale } from '@/i18n/context.js';
import { docsPath, type DocSlug } from '@/modules/public/docs/lib/product-docs-nav.js';
import { productDocsSource } from '@/modules/public/docs/lib/product-docs-source.js';

export type ProductDocsPageMeta = {
  title: string;
  description?: string;
};

type ProductDocFrontmatter = {
  title?: string;
  description?: string;
};

export function productDocsPageMeta(locale: Locale, slug: DocSlug): ProductDocsPageMeta | null {
  const page = productDocsSource.getPageByUrl(docsPath(slug), locale);
  if (!page) return null;
  const data = page.data as ProductDocFrontmatter;
  const title = data.title?.trim();
  if (!title) return null;
  const description = data.description?.trim();
  return { title, description: description || undefined };
}
