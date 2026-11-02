import { defineI18n } from 'fumadocs-core/i18n';
import { loader } from 'fumadocs-core/source';

import { docs as docsCollection } from '@/.source/server.js';

import type { Locale } from '@/i18n/context.js';

const productDocsI18n = defineI18n({
  defaultLanguage: 'en',
  languages: ['en', 'zh'],
  parser: 'dir',
  hideLocale: 'always',
});

type ProductDocFrontmatter = {
  sidebarTitle?: string;
};

/** Fumadocs page tree + URLs for `/docs/*` (locale from Basis i18n, not URL prefix). */
export const productDocsSource = loader({
  baseUrl: '/docs',
  i18n: productDocsI18n,
  source: docsCollection.toFumadocsSource(),
  pageTree: {
    transformers: [
      {
        file(node, filePath) {
          if (!filePath) return node;
          const file = this.storage.read(filePath);
          if (file?.format !== 'page') return node;
          const sidebarTitle = (file.data as ProductDocFrontmatter).sidebarTitle?.trim();
          if (!sidebarTitle) return node;
          return { ...node, name: sidebarTitle };
        },
      },
    ],
  },
});

export function productDocsPageTree(locale: Locale) {
  return productDocsSource.getPageTree(locale);
}
