import type { ReactNode } from 'react';
import { useI18n } from '@/i18n/context.js';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.js';
import { cn } from '@/lib/utils.js';

export interface DataTableColumn<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  hideBelow?: 'sm' | 'md' | 'lg';
  align?: 'left' | 'right' | 'center';
  width?: string;
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  rowKey: (row: T) => string | number;
  onRowClick?: (row: T) => void;
  /** DOM id on `<tr>` (e.g. deep-link scroll targets). */
  rowDomId?: (row: T) => string | undefined;
  rowClassName?: (row: T) => string | undefined;
  emptyMessage?: string;
  className?: string;
}

const hideBelowClasses: Record<NonNullable<DataTableColumn<unknown>['hideBelow']>, string> = {
  sm: 'hidden sm:table-cell',
  md: 'hidden md:table-cell',
  lg: 'hidden lg:table-cell',
};

const alignClasses = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
};

export function DataTable<T>({
  columns,
  data,
  rowKey,
  onRowClick,
  rowDomId,
  rowClassName,
  emptyMessage,
  className,
}: DataTableProps<T>) {
  const { t } = useI18n();
  const message = emptyMessage ?? t.core.common.noRecords;
  if (data.length === 0) {
    return (
      <div className={cn('py-10 text-center text-sm text-muted-foreground', className)}>
        {message}
      </div>
    );
  }

  return (
    <div className={cn('overflow-x-auto border border-line bg-bg-2', className)}>
      <Table className="min-w-[640px] border-separate border-spacing-0">
        <TableHeader>
          <TableRow className="border-b border-border hover:bg-transparent">
            {columns.map((col) => (
              <TableHead
                key={col.key}
                style={{ width: col.width }}
                className={cn(
                  'h-auto px-4 py-3 text-[10.5px] font-bold tracking-wide text-muted-foreground uppercase',
                  alignClasses[col.align ?? 'left'],
                  col.hideBelow && hideBelowClasses[col.hideBelow],
                )}
              >
                {col.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row) => (
            <TableRow
              key={rowKey(row)}
              id={rowDomId?.(row)}
              data-clickable={onRowClick ? 'true' : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={cn(
                'border-b border-border/60 last:border-0',
                onRowClick && 'cursor-pointer',
                rowClassName?.(row),
              )}
            >
              {columns.map((col) => (
                <TableCell
                  key={col.key}
                  className={cn(
                    'px-4 py-3 text-foreground whitespace-normal',
                    alignClasses[col.align ?? 'left'],
                    col.hideBelow && hideBelowClasses[col.hideBelow],
                  )}
                >
                  {col.render(row)}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
