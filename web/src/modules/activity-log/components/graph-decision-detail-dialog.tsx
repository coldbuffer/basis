import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { errorFromApiResponse } from '@/lib/errors/api-error.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { useI18n } from '@/i18n/context.js';
import {
  fmt,
  formatLocaleDateTime,
  formatLocaleFixedDecimals,
  requestFailedStatusMessage,
} from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import {
  type DecisionRow,
  decisionListTitle,
  formatDecisionReasoningBody,
  reviewItemIdFromDecision,
} from '@/modules/decisions/lib/decision-display.js';
import {
  decisionCategoryLabel,
  decisionChainRelationshipLabel,
  decisionChainStepTypeLabel,
  decisionOutcomeLabel,
} from '@/modules/decisions/i18n/screen-copy.js';
import { reviewItemPath } from '@/modules/review/lib/review-url-state.js';
import { cn } from '@/lib/utils.js';

type ChainStep = {
  id: string;
  relationship: string;
  content?: string;
  type?: string;
};

function outcomeBadgeClass(outcome: string) {
  const o = outcome.toLowerCase();
  if (o.includes('approv') || o.includes('accept')) return 'bg-ok/15 text-ok';
  if (o.includes('reject') || o.includes('denied') || o.includes('fail')) return 'bg-destructive/15 text-destructive';
  if (o.includes('defer') || o.includes('pending') || o.includes('review')) return 'bg-warn/15 text-warn';
  return 'bg-muted text-muted-foreground';
}

export function GraphDecisionDetailDialog({
  workspaceId,
  decisionId,
  open,
  onOpenChange,
}: {
  workspaceId: string;
  decisionId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t, locale } = useI18n();
  const al = t.activity_log.page;
  const dec = t.decisions.page;
  const apiError = useApiErrorMessage();

  const [row, setRow] = useState<DecisionRow | null>(null);
  const [chain, setChain] = useState<ChainStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const ctrlRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!open || !decisionId?.trim()) {
      setRow(null);
      setChain([]);
      setError('');
      return;
    }
    const id = decisionId.trim();
    ctrlRef.current?.abort();
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;

    setLoading(true);
    setError('');
    setRow({ decision_id: id });
    setChain([]);

    void (async () => {
      try {
        const [listRes, chainRes] = await Promise.all([
          workspaceOpenApiResponse('GET', workspaceId, 'decisions', { signal: ctrl.signal }),
          workspaceOpenApiResponse('GET', workspaceId, `decisions/${encodeURIComponent(id)}/chain`, {
            signal: ctrl.signal,
          }),
        ]);

        if (!ctrl.signal.aborted) {
          const listData = await listRes.json().catch(() => []);
          if (listRes.ok && Array.isArray(listData)) {
            const match = listData.find((d: DecisionRow) => d.decision_id === id);
            if (match) setRow(match);
          }

          const chainData = await chainRes.json().catch(() => ({}));
          if (!chainRes.ok) {
            throw errorFromApiResponse(
              chainRes.status,
              chainData,
              requestFailedStatusMessage(locale as Locale, chainRes.status),
              locale as Locale,
            );
          }
          if (chainRes.status === 207) {
            setError(chainData.message || dec.partial_load_chain);
          }
          setChain(Array.isArray(chainData.chain) ? chainData.chain : []);
        }
      } catch (e) {
        if (e instanceof Error && e.name !== 'AbortError' && !ctrl.signal.aborted) {
          setError(apiError(e));
        }
      } finally {
        if (!ctrl.signal.aborted) setLoading(false);
      }
    })();

    return () => ctrl.abort();
  }, [apiError, dec.partial_load_chain, decisionId, locale, open, workspaceId]);

  const selected = row;
  const linkedReviewItemId = selected ? reviewItemIdFromDecision(selected) : null;
  const reasoningBody = selected ? formatDecisionReasoningBody(selected.reasoning) : '';
  const title = selected ? decisionListTitle(selected, dec) : al.decision_detail_title;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[min(90vh,42rem)] max-w-lg overflow-y-auto sm:max-w-xl"
        data-testid="graph-decision-detail-dialog"
      >
        <DialogHeader>
          <DialogTitle className="text-left text-base leading-snug">{title}</DialogTitle>
        </DialogHeader>

        {loading && !selected?.scenario && !selected?.reasoning ? (
          <div className="flex justify-center py-10">
            <Spinner className="size-6" />
          </div>
        ) : null}

        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {selected ? (
          <div className="space-y-4 text-sm">
            <div>
              <p className="font-mono text-[11px] text-muted-foreground break-all">
                {dec.decision_id_label}: {selected.decision_id}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                {selected.category ? (
                  <span className="rounded-md border border-border px-1.5 py-0.5 font-mono">
                    {decisionCategoryLabel(dec, selected.category)}
                  </span>
                ) : null}
                {selected.outcome ? (
                  <span
                    className={cn(
                      'rounded-md px-1.5 py-0.5 text-[10px] font-medium uppercase',
                      outcomeBadgeClass(selected.outcome),
                    )}
                  >
                    {decisionOutcomeLabel(dec, selected.outcome)}
                  </span>
                ) : null}
                {selected.timestamp ? (
                  <span>
                    {dec.recorded_at}:{' '}
                    {formatLocaleDateTime(locale as Locale, selected.timestamp, {
                      dateStyle: 'medium',
                      timeStyle: 'short',
                    })}
                  </span>
                ) : null}
                {typeof selected.confidence === 'number' && selected.confidence > 0 ? (
                  <span>
                    {dec.confidence_label}:{' '}
                    {formatLocaleFixedDecimals(locale as Locale, selected.confidence, 2)}
                  </span>
                ) : null}
              </div>
              <div className="mt-2 flex flex-wrap gap-2">
                {linkedReviewItemId ? (
                  <Link
                    to={reviewItemPath(workspaceId, linkedReviewItemId)}
                    className="text-xs text-primary underline-offset-2 hover:underline"
                  >
                    {dec.open_review_item}
                  </Link>
                ) : null}
              </div>
            </div>

            {selected.scenario?.trim() && selected.scenario.trim() !== decisionListTitle(selected, dec) ? (
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {dec.summary_heading}
                </div>
                <p className="mt-1 leading-relaxed">{selected.scenario}</p>
              </div>
            ) : null}

            {reasoningBody ? (
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {dec.reasoning_heading}
                </div>
                <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-muted/30 p-3 font-mono text-[11px] leading-relaxed">
                  {reasoningBody}
                </pre>
              </div>
            ) : null}

            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {dec.causal_chain}
                {chain.length > 0 && !loading ? (
                  <span className="ml-2 font-normal normal-case text-muted-foreground">
                    {chain.length === 1
                      ? dec.chain_step_count_one
                      : fmt(dec.chain_step_count, { count: chain.length })}
                  </span>
                ) : null}
              </div>
              {loading ? (
                <div className="flex justify-center py-6">
                  <Spinner className="size-5" />
                </div>
              ) : chain.length === 0 ? (
                <p className="mt-2 text-xs text-muted-foreground">{dec.chain_empty_body}</p>
              ) : (
                <ol className="mt-2 space-y-2">
                  {chain.map((step, i) => (
                    <li
                      key={`${step.id}-${i}`}
                      className="rounded-md border border-border border-l-2 border-l-primary/40 px-3 py-2 text-xs"
                    >
                      {step.type ? (
                        <div className="mb-0.5 font-mono text-[10px] font-bold uppercase text-primary">
                          {decisionChainStepTypeLabel(dec, step.type)}
                        </div>
                      ) : null}
                      <div className="font-medium">
                        {step.content?.trim() ||
                          (step.relationship
                            ? decisionChainRelationshipLabel(dec, step.relationship)
                            : step.id)}
                      </div>
                      {i < chain.length - 1 && chain[i + 1]?.relationship ? (
                        <div className="mt-1 text-[10px] text-muted-foreground">
                          ↓ {decisionChainRelationshipLabel(dec, chain[i + 1].relationship)}
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        ) : null}

        <div className="flex justify-end pt-2">
          <Button type="button" variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            {al.decision_detail_close}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
