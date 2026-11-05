import { formatNodeRefDetail } from '@/lib/workspace/format-node-ref.js';
import { cn } from '@/lib/utils.js';

/** One-line entity display; full UUID is available via native title tooltip or optional `showId`. */
export function EntityRefLine({
  id,
  labels,
  className,
  showId = false,
}: {
  id: string;
  labels: Record<string, string | null | undefined>;
  className?: string;
  showId?: boolean;
}) {
  const { title, subtitle } = formatNodeRefDetail(id, labels);
  return (
    <div className={cn('min-w-0', className)} title={subtitle ? `${title}\n${subtitle}` : title}>
      <div className="text-sm leading-snug text-foreground">{title}</div>
      {showId && subtitle ? (
        <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
          {subtitle}
        </div>
      ) : null}
    </div>
  );
}
