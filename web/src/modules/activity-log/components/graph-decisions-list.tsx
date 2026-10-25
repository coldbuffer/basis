import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button.js';
import { Input } from '@/components/ui/input.js';
import { Spinner } from '@/components/ui/spinner.js';
import { EmptyState } from '@/components/app/shared/console/index.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { useI18n } from '@/i18n/context.js';
import { fmt } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import {
  type DecisionRow,
  decisionListPreview,
  decisionListTitle,
  formatDecisionReasoningBody,
} from '@/modules/decisions/lib/decision-display.js';
import {
  decisionCategoryLabel,
  decisionOutcomeLabel,
} from '@/modules/decisions/i18n/screen-copy.js';
import { cn } from '@/lib/utils.js';

const DECISIONS_FETCH_LIMIT = 200;

export function GraphDecisionsList({
  workspaceId,
  enabled,
  initialFilter = '',
  onSelectDecision,
  className,
}: {
  workspaceId: string;
  enabled: boolean;
  initialFilter?: string;
  onSelectDecision: (decisionId: string) => void;
  className?: string;
}) {
  const { t, locale } = useI18n();
  const p = t.activity_log.page;
  const dec = t.decisions.page;
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();

  const [decisions, setDecisions] = useState<DecisionRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState(initialFilter);

  useEffect(() => {
    if (enabled) setFilter(initialFilter);
  }, [enabled, initialFilter]);

  useEffect(() => {
    if (!enabled) return;
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    void workspaceOpenApiGET<DecisionRow[]>(workspaceId, 'decisions', {
      signal: ctrl.signal,
      params: { query: { limit: DECISIONS_FETCH_LIMIT } },
    })
      .then((data) => {
        if (!ctrl.signal.aborted) {
          setDecisions(Array.isArray(data) ? data : []);
        }
      })
      .catch((err) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        if (!ctrl.signal.aborted) {
          setDecisions([]);
          setError(formatUserFacingApiError(err, locale as Locale));
        }
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [enabled, locale, workspaceId]);

  const filtered = useMemo(() => {
    const q = filter.toLowerCase().trim();
    if (!q) return decisions;
    return decisions.filter((d) => {
      const hay = [
        d.decision_id,
        d.category,
        d.outcome,
        d.scenario,
        d.reasoning,
        formatDecisionReasoningBody(d.reasoning),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(q);
    });
  }, [decisions, filter]);

  if (!capsLoading && caps && !caps.graph_runtime) {
    return <WorkspaceUnavailable workspaceId={workspaceId} feature="graph" />;
  }

  return (
    <div className={cn('flex min-h-0 flex-col', className)} data-testid="graph-decisions-list">
      <div className="border-b border-border px-4 py-2">
        <div className="relative max-w-md">
          <PublicIcon
            name="search-01"
            size={12}
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            type="search"
            className="h-9 pl-9 text-xs"
            placeholder={dec.filter_placeholder}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">{p.graph_decisions_list_hint}</p>
      </div>

      {error ? (
        <p className="border-b border-border px-4 py-3 text-sm text-destructive">{error}</p>
      ) : null}

      {loading ? (
        <div className="flex justify-center py-16">
          <Spinner className="size-6" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          title={decisions.length === 0 ? dec.empty_list : dec.no_matches}
          description={
            decisions.length === 0 ? p.graph_decisions_list_empty : dec.adjust_filter
          }
        />
      ) : (
        <ul className="divide-y divide-border overflow-y-auto">
          {filtered.map((row) => (
            <li key={row.decision_id}>
              <Button
                type="button"
                variant="ghost"
                data-testid={`decision-list-item-${row.decision_id}`}
                className="h-auto w-full justify-start rounded-none px-4 py-3 text-left font-normal"
                onClick={() => onSelectDecision(row.decision_id)}
              >
                <div className="text-sm font-medium">{decisionListTitle(row, dec)}</div>
                {decisionListPreview(row) ? (
                  <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                    {decisionListPreview(row)}
                  </div>
                ) : null}
                <div className="mt-1 flex flex-wrap gap-2 text-[11px] text-muted-foreground">
                  {row.category ? (
                    <span>{decisionCategoryLabel(dec, row.category)}</span>
                  ) : null}
                  {row.outcome ? (
                    <span>{decisionOutcomeLabel(dec, row.outcome)}</span>
                  ) : null}
                </div>
                <div className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
                  {row.decision_id}
                </div>
              </Button>
            </li>
          ))}
        </ul>
      )}

      {!loading && decisions.length > 0 ? (
        <p className="border-t border-border px-4 py-2 text-[10px] text-muted-foreground">
          {decisions.length === 1
            ? dec.decision_count_one
            : fmt(dec.decision_count, { count: decisions.length })}
        </p>
      ) : null}
    </div>
  );
}
