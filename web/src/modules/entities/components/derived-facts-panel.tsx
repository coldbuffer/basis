import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card } from '@/components/app/shared/console/Card.js';
import {
  DerivedFactCard,
  type DerivedFactView,
} from '@/components/app/shared/workspace/derived-fact-card.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { workspaceAnalyzeHubPath } from '@/modules/analyze/lib/hub-route.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

export type { DerivedFactView } from '@/components/app/shared/workspace/derived-fact-card.js';

type DerivedFactRow = DerivedFactView & {
  recorded_at: string;
};

export function DerivedFactsPanel({ workspaceId }: { workspaceId: string }) {
  const { t, locale } = useI18n();
  const l = t.entities.ledger;
  const [facts, setFacts] = useState<DerivedFactRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void workspaceOpenApiGET<{ derived_facts: DerivedFactRow[] }>(workspaceId, 'ledger/derived-facts', {
      params: { query: { limit: 12 } },
    })
      .then((data) => {
        if (!cancelled) setFacts(data.derived_facts ?? []);
      })
      .catch(() => {
        if (!cancelled) setFacts([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  const labelIds = facts.flatMap((f) =>
    [f.subject_id, f.object_entity_id].filter((id): id is string => Boolean(id)),
  );
  const labels = useWorkspaceNodeLabels(workspaceId, labelIds);

  return (
    <aside className="flex h-80 min-h-0 w-full shrink-0 flex-col overflow-hidden min-[960px]:h-full min-[960px]:w-auto">
      <Card padding="none" className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="flex shrink-0 items-start gap-3 border-b border-border px-4 py-3">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-acc-soft text-acc">
            <PublicIcon name="lightning-01" size={16} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">{l.recent_derived_facts}</h3>
              {!loading ? (
                <Badge variant="secondary" className="tabular-nums">
                  {formatLocaleNumber(locale as Locale, facts.length)}
                </Badge>
              ) : null}
            </div>
            <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
              {l.recent_derived_facts_hint}
            </p>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto p-3">
          {loading ? (
            <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              {l.loading_derived_facts}
            </div>
          ) : facts.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center px-4 py-8 text-center">
              <span className="mb-3 flex size-10 items-center justify-center rounded-full bg-bg-3 text-acc">
                <PublicIcon name="magic-wand" size={18} />
              </span>
              <p className="text-sm font-semibold">{l.no_derived_facts}</p>
              <p className="mt-1 max-w-[16rem] text-xs leading-relaxed text-muted-foreground">
                {l.no_derived_facts_hint}
              </p>
            </div>
          ) : (
            <ul className="space-y-2">
              {facts.map((fact) => (
                <DerivedFactCard key={fact.id} workspaceId={workspaceId} fact={fact} labels={labels} />
              ))}
            </ul>
          )}
        </div>
        <div className="shrink-0 border-t border-border p-2">
          <Button variant="ghost" size="sm" className="w-full justify-between" asChild>
            <Link to={workspaceAnalyzeHubPath(workspaceId, 'reasoning')}>
              {l.open_reasoning}
              <PublicIcon name="arrow-right" size={14} />
            </Link>
          </Button>
        </div>
      </Card>
    </aside>
  );
}
