import { useLocation } from 'react-router-dom';

import { DocsFumadocsPage } from '@/components/app/marketing/docs/docs-fumadocs-page.js';
import { DocsNotFound } from '@/components/app/marketing/docs/docs-not-found.js';
import { DocsShell } from '@/components/app/marketing/docs/docs-shell.js';
import { DOC_SLUGS, docSlugFromParam, type DocSlug } from '@/modules/public/docs/lib/product-docs-nav.js';

function isDocSlug(value: string): value is DocSlug {
  return (DOC_SLUGS as readonly string[]).includes(value);
}

export function DocsPage() {
  const { pathname } = useLocation();
  const slugParam = pathname.replace(/^\/docs\/?/, '').split('/')[0];

  if (slugParam && !isDocSlug(slugParam)) {
    return (
      <DocsShell>
        <DocsNotFound path={pathname} />
      </DocsShell>
    );
  }

  const slug = docSlugFromParam(slugParam || undefined);

  return (
    <DocsShell activeSlug={slug}>
      <DocsFumadocsPage slug={slug} />
    </DocsShell>
  );
}
