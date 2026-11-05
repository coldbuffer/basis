import type { ReactNode } from 'react';
import { PageHeader, type Crumb } from '@/components/app/shared/console/PageHeader.js';
import { cn } from '@/lib/utils.js';

export type ConsolePageLayoutProps = {
  crumbs: Crumb[];
  /** Short description under the breadcrumb. */
  subtitle?: ReactNode;
  /** Secondary line: role, hint, etc. */
  meta?: ReactNode;
  /** Primary actions aligned to the header row (create, export, …). */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
};

/**
 * Standard console page shell: breadcrumb → optional subtitle/meta → optional action row → content.
 */
export function ConsolePageLayout({
  crumbs,
  subtitle,
  meta,
  actions,
  children,
  className,
}: ConsolePageLayoutProps) {
  return (
    <div className={cn('flex min-h-0 flex-1 flex-col gap-4', className)}>
      <header className="flex flex-col gap-2 border-b border-border/60 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1">
          <PageHeader crumbs={crumbs} />
          {subtitle ? (
            <div className="min-w-0 text-xs leading-relaxed text-muted-foreground">{subtitle}</div>
          ) : null}
          {meta ? <div className="text-xs text-muted-foreground">{meta}</div> : null}
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </header>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
