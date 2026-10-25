import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button.js";
import { Spinner } from "@/components/ui/spinner.js";
import {
  activityLogBrowseDecisionsPath,
  reviewDecisionPath,
} from '@/modules/review/lib/review-url-state.js';
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import type { LocaleMessages } from "@/i18n/en.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";
import { wsApiErrorMessage, parseWsJson } from '@/lib/workspace/ws-api-error';
import {
  decisionCategoryLabel,
  decisionOutcomeLabel,
} from "@/modules/decisions/i18n/screen-copy.js";
import type { GraphScreenLocale } from '../i18n/screen-copy.js';
import { inspectorCopy } from '../i18n/graph-inspector-copy.js';

type DecisionRow = {
  decision_id: string;
  category?: string;
  outcome?: string;
};

function decisionMentionsNode(decision: DecisionRow, nodeId: string): boolean {
  const needle = nodeId.toLowerCase();
  if (decision.decision_id.toLowerCase().includes(needle)) return true;
  const blob = JSON.stringify(decision).toLowerCase();
  return blob.includes(needle);
}

export function GraphInspectorDecisions({
  workspaceId,
  nodeId,
  enabled,
  locale = "en",
}: {
  workspaceId: string;
  nodeId: string;
  enabled: boolean;
  locale?: GraphScreenLocale;
}) {
  const [loading, setLoading] = useState(false);
  const [decisions, setDecisions] = useState<DecisionRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !nodeId.trim()) {
      setDecisions([]);
      setError(null);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    const fallback = inspectorCopy(locale, "decisionsLoadFailed");
    void workspaceOpenApiResponse('GET', workspaceId, 'decisions', {
      params: { query: { limit: 100 } },
      signal: ctrl.signal,
    })
      .then(async (response) => {
        const data = await parseWsJson<DecisionRow[]>(response, fallback);
        if (!ctrl.signal.aborted) setDecisions(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        if (err instanceof Error && err.name === "AbortError") return;
        if (!ctrl.signal.aborted) {
          setDecisions([]);
          setError(wsApiErrorMessage(err, locale));
        }
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [enabled, workspaceId, locale, nodeId]);

  const related = useMemo(
    () => decisions.filter((row) => decisionMentionsNode(row, nodeId)).slice(0, 5),
    [decisions, nodeId],
  );

  const reviewDecisionsUrl = activityLogBrowseDecisionsPath(workspaceId, { q: nodeId });
  const localeMessages = messagesForLocale(locale);
  const decisionsCopy = localeMessages.decisions.page;
  const emptyCell = localeMessages.core.common.emptyCell;

  if (!enabled) return null;

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3.5 shadow-sm">
      <div className="flex items-center gap-2">
        <PublicIcon name="scales" size={14} className="text-muted-foreground" />
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {inspectorCopy(locale, "relatedDecisions")}
        </h3>
      </div>
      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Spinner className="size-3.5" />
          {inspectorCopy(locale, "decisionsLoading")}
        </div>
      ) : error ? (
        <p className="text-xs text-muted-foreground">{error}</p>
      ) : related.length === 0 ? (
        <p className="text-xs leading-relaxed text-muted-foreground">
          {inspectorCopy(locale, "noDecisions")}
        </p>
      ) : (
        <ul className="space-y-2 text-xs">
          {related.map((row) => (
            <li key={row.decision_id} className="rounded-md border border-border/80 bg-background/60 px-2.5 py-2">
              <Link
                to={reviewDecisionPath(workspaceId, row.decision_id)}
                className="font-mono font-medium break-all text-foreground underline-offset-2 hover:underline"
              >
                {row.decision_id}
              </Link>
              <div className="mt-1 text-muted-foreground">
                {[
                  row.category ? decisionCategoryLabel(decisionsCopy, row.category) : "",
                  row.outcome ? decisionOutcomeLabel(decisionsCopy, row.outcome) : "",
                ]
                  .filter(Boolean)
                  .join(" · ") || emptyCell}
              </div>
            </li>
          ))}
        </ul>
      )}
      <Button variant="outline" size="sm" className="justify-start" asChild>
        <Link to={reviewDecisionsUrl}>
          {inspectorCopy(locale, "openDecisionsReview")}
        </Link>
      </Button>
    </section>
  );
}
