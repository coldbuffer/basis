import { useMemo } from 'react';
import { DataPanel, DataPanelBody, DataPanelHeader } from '@/components/app/shared/console/index.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import { cn } from '@/lib/utils.js';

export type CategoryBreakdownRow = {
  category: string;
  total: number;
  enabled: number;
};

type Props = {
  rows: CategoryBreakdownRow[];
  maxBars?: number;
  onSelectCategory?: (category: string) => void;
  selectedCategory?: string;
};

export function PlatformConnectorCategoryBreakdown({
  rows,
  maxBars = 12,
  onSelectCategory,
  selectedCategory,
}: Props) {
  const { t, locale } = useI18n();
  const ps = t.admin_settings.page.connectors;

  const top = useMemo(() => {
    return [...rows].sort((a, b) => b.total - a.total).slice(0, maxBars);
  }, [maxBars, rows]);

  const maxTotal = top[0]?.total ?? 1;

  if (top.length === 0) return null;

  return (
    <DataPanel>
      <DataPanelHeader title={ps.category_breakdown_title} subtitle={ps.category_breakdown_subtitle} />
      <DataPanelBody className="space-y-3">
        {top.map((row) => {
          const widthPct = Math.max(4, Math.round((row.total / maxTotal) * 100));
          const enabledPct =
            row.total > 0 ? Math.round((row.enabled / row.total) * 100) : 0;
          const active = selectedCategory === row.category;
          return (
            <button
              key={row.category}
              type="button"
              className={cn(
                'w-full rounded-md px-2 py-1.5 text-left transition-colors',
                onSelectCategory ? 'hover:bg-muted/60' : 'cursor-default',
                active && 'bg-muted/80 ring-1 ring-border',
              )}
              onClick={() => onSelectCategory?.(row.category)}
            >
              <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                <span className="font-medium capitalize text-foreground">{row.category}</span>
                <span className="tabular-nums text-muted-foreground">
                  {fmt(ps.category_breakdown_counts, {
                    enabled: formatLocaleNumber(locale, row.enabled),
                    total: formatLocaleNumber(locale, row.total),
                  })}
                </span>
              </div>
              <div className="relative h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-primary/25"
                  style={{ width: `${widthPct}%` }}
                />
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-primary"
                  style={{ width: `${Math.round((widthPct * enabledPct) / 100)}%` }}
                />
              </div>
            </button>
          );
        })}
      </DataPanelBody>
    </DataPanel>
  );
}
