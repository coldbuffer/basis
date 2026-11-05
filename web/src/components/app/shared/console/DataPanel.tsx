import type { IconType } from 'react-icons';
import type { HTMLAttributes, ReactNode } from 'react';
import { Card, CardSubtitle } from '@/components/app/shared/console/Card.js';
import { getPublicIconComponent } from '@/lib/marketing/public-icon-map.js';
import { cn } from '@/lib/utils.js';

export function DataPanel({
  className,
  children,
  ...rest
}: { className?: string; children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('flex flex-col gap-2', className)} {...rest}>
      {children}
    </div>
  );
}

export function DataPanelHeader({
  icon,
  iconName,
  title,
  subtitle,
  meta,
  actions,
  className,
}: {
  icon?: IconType;
  iconName?: string;
  title?: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  if (!icon && !iconName && !title && !subtitle && !meta && !actions) return null;

  const hasSubtitle = Boolean(subtitle);
  const HeaderIcon = icon ?? (iconName ? getPublicIconComponent(iconName) : null);

  return (
    <div
      className={cn(
        'flex justify-between gap-3',
        hasSubtitle ? 'items-start' : 'items-center',
        className,
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2 leading-none">
          {HeaderIcon ? (
            <HeaderIcon
              size={16}
              aria-hidden
              className="size-4 shrink-0 text-signal [&_svg]:block"
            />
          ) : null}
          {title ? (
            <span className="font-['Noto_Sans_SC',sans-serif] text-sm font-bold leading-none text-foreground">
              {title}
            </span>
          ) : null}
        </div>
        {subtitle ? <CardSubtitle className="mt-1 text-[11px]">{subtitle}</CardSubtitle> : null}
      </div>
      {meta || actions ? (
        <div className="flex shrink-0 items-center gap-3">
          {meta}
          {actions}
        </div>
      ) : null}
    </div>
  );
}

export function DataPanelBody({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <Card padding="none" className="overflow-hidden">
      <div className={cn(padded && 'p-4', className)}>{children}</div>
    </Card>
  );
}
