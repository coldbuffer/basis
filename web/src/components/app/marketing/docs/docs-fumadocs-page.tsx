import { Suspense, useMemo } from 'react';

import { DocsPageFooter } from '@/components/app/marketing/docs/docs-page-footer.js';
import { DocsPageToc } from '@/components/app/marketing/docs/docs-page-toc.js';
import { useI18n } from '@/i18n/context.js';
import { productDocsMdx, productDocsMdxPath } from '@/modules/public/docs/lib/product-docs-mdx-loader.js';
import { productDocsNeighbours } from '@/modules/public/docs/lib/product-docs-neighbours.js';
import { productDocsPageMeta } from '@/modules/public/docs/lib/product-docs-page-meta.js';
import type { DocSlug } from '@/modules/public/docs/lib/product-docs-nav.js';
import { cn } from '@/lib/utils.js';

type DocsFumadocsPageProps = {
  slug: DocSlug;
  className?: string;
};

function DocsMdxBody({ path }: { path: string }) {
  return productDocsMdx.useContent(path);
}

export function DocsFumadocsPage({ slug, className }: DocsFumadocsPageProps) {
  const { locale, t } = useI18n();
  const path = useMemo(() => productDocsMdxPath(locale, slug), [locale, slug]);
  const pageMeta = useMemo(() => productDocsPageMeta(locale, slug), [locale, slug]);
  const neighbours = useMemo(() => productDocsNeighbours(locale, slug), [locale, slug]);

  return (
    <div className={cn('min-w-0 w-full', className)}>
      <header className="mb-8 border-b border-border pb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          {pageMeta?.title ?? t.core.common.ellipsis}
        </h1>
        {pageMeta?.description ? (
          <p className="mt-3 text-base leading-relaxed text-muted-foreground">{pageMeta.description}</p>
        ) : null}
      </header>
      <div className="flex flex-col gap-6 xl:flex-row xl:gap-10">
        <div className="xl:hidden">
          <DocsPageToc />
        </div>
        <div className="min-w-0 flex-1">
          <article data-doc-article className="min-w-0 w-full text-sm">
            <Suspense fallback={<p className="text-muted-foreground">{t.core.common.ellipsis}</p>}>
              <DocsMdxBody path={path} />
            </Suspense>
          </article>
          <DocsPageFooter neighbours={neighbours} />
        </div>
        <aside className="hidden w-60 shrink-0 xl:block">
          <div className="sticky top-8">
            <DocsPageToc />
          </div>
        </aside>
      </div>
    </div>
  );
}
