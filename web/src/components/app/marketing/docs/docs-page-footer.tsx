import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useI18n } from '@/i18n/context.js';
import type { DocsAdjacentPage } from '@/modules/public/docs/lib/product-docs-neighbours.js';
import { resourceCardSurfaceClass } from '@/lib/ui-classes/card-surface.js';
import { cn } from '@/lib/utils.js';

type DocsPageFooterProps = {
  neighbours: { previous?: DocsAdjacentPage; next?: DocsAdjacentPage };
};

function PagerCard({
  direction,
  page,
  label,
}: {
  direction: 'previous' | 'next';
  page: DocsAdjacentPage;
  label: string;
}) {
  const isNext = direction === 'next';
  return (
    <Link
      to={page.href}
      className={cn(
        resourceCardSurfaceClass,
        'group flex flex-col rounded-lg px-4 py-3 transition-colors hover:bg-muted/80',
        isNext && 'sm:col-start-2 sm:text-right sm:items-end',
      )}
    >
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        {!isNext ? <ChevronLeft className="size-3.5 shrink-0" aria-hidden /> : null}
        {label}
        {isNext ? <ChevronRight className="size-3.5 shrink-0" aria-hidden /> : null}
      </span>
      <span className="mt-1 text-sm font-medium text-foreground group-hover:underline">
        {page.name}
      </span>
    </Link>
  );
}

export function DocsPageFooter({ neighbours }: DocsPageFooterProps) {
  const { t } = useI18n();
  const hasPager = neighbours.previous ?? neighbours.next;

  if (!hasPager) return null;

  return (
    <footer className="mt-10 w-full border-t border-border pt-6">
      <nav className="grid gap-3 sm:grid-cols-2" aria-label={t.docs.page.pager_aria}>
        {neighbours.previous ? (
          <PagerCard direction="previous" page={neighbours.previous} label={t.docs.page.previous_page} />
        ) : (
          <div className="hidden sm:block" aria-hidden />
        )}
        {neighbours.next ? (
          <PagerCard direction="next" page={neighbours.next} label={t.docs.page.next_page} />
        ) : null}
      </nav>
    </footer>
  );
}
