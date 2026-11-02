import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import {
  decisionChainRelationshipLabel,
  decisionChainStepTypeLabel,
} from '@/modules/workspace/decisions/i18n/screen-copy.js';
import { useI18n } from '@/i18n/context.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { reviewDecisionPath } from '@/modules/workspace/review/lib/review-url-state.js';

type ChainStep = {
  id: string;
  relationship?: string;
  content?: string;
  type?: string;
};

type ChainResponse = {
  chain?: ChainStep[];
};

type ReviewDecisionNarrativeProps = {
  workspaceId: string;
  decisionId: string;
  /** Sidebar block vs compact block inside a review item / banner. */
  variant?: 'sidebar' | 'embedded';
};

const MAX_STEPS = 4;

export function ReviewDecisionNarrative({
  workspaceId,
  decisionId,
  variant = 'sidebar',
}: ReviewDecisionNarrativeProps) {
  const { t } = useI18n();
  const r = t.review.queue;
  const dec = t.decisions.page;
  const [chain, setChain] = useState<ChainStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    setError(false);
    workspaceOpenApiGET<ChainResponse>(workspaceId, `decisions/${encodeURIComponent(decisionId)}/chain`)
      .then((body) => {
        if (ctrl.signal.aborted) return;
        setChain(Array.isArray(body.chain) ? body.chain : []);
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [workspaceId, decisionId]);

  const visible = chain.slice(0, MAX_STEPS);
  const truncated = chain.length > MAX_STEPS;

  const embedded = variant === 'embedded';

  return (
    <section
      className={
        embedded
          ? 'mt-3 rounded-md border border-border bg-muted/20 px-3 py-2.5'
          : 'shrink-0 border-b border-border px-4 py-3'
      }
      data-testid={embedded ? 'review-item-decision-narrative' : 'review-decision-narrative'}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          {r.decision_narrative_title}
        </h3>
        <Link
          to={reviewDecisionPath(workspaceId, decisionId)}
          className="shrink-0 text-[11px] text-foreground underline-offset-2 hover:underline"
          data-testid="review-decision-narrative-open"
        >
          {r.decision_narrative_open_full}
        </Link>
      </div>
      <p className="mt-1 font-mono text-[10px] text-muted-foreground">{decisionId}</p>

      {loading ? (
        <p className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
          <PublicIcon name="loader-01" size={12} className="animate-spin" />
          {t.core.common.loading}
        </p>
      ) : error ? (
        <p className="mt-2 text-[11px] text-destructive">{dec.partial_load_chain}</p>
      ) : visible.length === 0 ? (
        <p className="mt-2 text-[11px] leading-snug text-muted-foreground">{dec.chain_empty_body}</p>
      ) : (
        <ol className="mt-2 space-y-2">
          {visible.map((step, index) => (
            <li key={`${step.id}-${index}`} className="rounded-md border border-border bg-muted/30 px-2.5 py-2">
              {step.type ? (
                <div className="font-mono text-[9px] font-semibold uppercase tracking-wide text-primary">
                  {decisionChainStepTypeLabel(dec, step.type)}
                </div>
              ) : null}
              <p className="text-[11px] leading-snug text-foreground">{step.content || step.id}</p>
              {index < visible.length - 1 && chain[index + 1]?.relationship ? (
                <p className="mt-1.5 text-[10px] italic text-muted-foreground">
                  {decisionChainRelationshipLabel(dec, chain[index + 1]?.relationship ?? '')}
                </p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
      {truncated ? (
        <p className="mt-2 text-[10px] text-muted-foreground">{r.decision_narrative_truncated}</p>
      ) : null}
    </section>
  );
}
