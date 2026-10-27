import { useMemo } from 'react';

import { useI18n } from '@/i18n/context.js';
import { processingOptionsSummaryLines } from '@/modules/processing/lib/processing-options-summary.js';

export function ProcessingOptionsSnapshot({
  options,
  summaryTitle,
  summaryTestId,
  jsonTestId,
  className,
  preClassName = 'mt-1 max-h-48 overflow-auto rounded-md bg-muted p-3 text-xs',
}: {
  options: Record<string, unknown>;
  /** When set, shown above the summary list (e.g. pipeline preview in Sources dialog). */
  summaryTitle?: string;
  summaryTestId?: string;
  jsonTestId?: string;
  className?: string;
  preClassName?: string;
}) {
  const { t } = useI18n();
  const p = t.processing.jobs;
  const lines = useMemo(
    () => processingOptionsSummaryLines(options, p),
    [options, p],
  );
  const jsonLabel = lines.length > 0 ? p.options_snapshot_raw : p.options_snapshot;

  return (
    <div className={className}>
      {summaryTitle && lines.length > 0 ? (
        <p className="text-xs font-medium text-foreground">{summaryTitle}</p>
      ) : null}
      {lines.length > 0 ? (
        <ul
          className="mt-1 space-y-0.5 text-xs text-muted-foreground"
          data-testid={summaryTestId}
        >
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
      <p
        className={
          lines.length > 0 || summaryTitle
            ? 'mt-3 text-xs font-medium text-muted-foreground'
            : 'text-xs font-medium text-muted-foreground'
        }
      >
        {jsonLabel}
      </p>
      <pre className={preClassName} data-testid={jsonTestId}>
        {JSON.stringify(options, null, 2)}
      </pre>
    </div>
  );
}
