import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  DataPanel,
  DataPanelBody,
  DataPanelToolbar,
  EmptyState,
} from '@/components/app/shared/console/index.js';
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
import { workspaceAnalyzeHubPath } from '@/modules/workspace/analyze/lib/hub-route.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

export type { DerivedFactView } from '@/components/app/shared/workspace/derived-fact-card.js';

type DerivedFactRow = DerivedFactView & {
  recorded_at: string;
};

export function DerivedFactsPanel({
  workspaceId,
  toolbarPrefix,
}: {
  workspaceId: string;
  toolbarPrefix?: React.ReactNode;
}) {
  const { t, locale } = useI18n();
  const l = t.entities.ledger;
  const [facts, setFacts] = useState<DerivedFactRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void workspaceOpenApiGET<{ derived_facts: DerivedFactRow[] }>(workspaceId, 'ledger/derived-facts', {
      params: { query: { limit: 24 } },
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
    <DataPanel>
      <DataPanelToolbar
        className="flex-wrap gap-y-2"
        search={
          toolbarPrefix ? (
            <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">{toolbarPrefix}</div>
          ) : undefined
        }
        actions={
          <Button variant="outline" size="sm" asChild>
            <Link to={workspaceAnalyzeHubPath(workspaceId, 'reasoning')}>
              {l.open_reasoning}
              <PublicIcon name="arrow-right" size={13} />
            </Link>
          </Button>
        }
      />

      <DataPanelBody padded={false} className="mt-2">
        <div className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-2.5">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-medium text-foreground">{l.recent_derived_facts}</h3>
            {!loading && facts.length > 0 ? (
              <Badge variant="secondary" className="text-[11px] font-normal tabular-nums">
                {formatLocaleNumber(locale as Locale, facts.length)}
              </Badge>
            ) : null}
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-xs text-muted-foreground">
            <Spinner className="size-4" />
            {l.loading_derived_facts}
          </div>
        ) : facts.length === 0 ? (
          <EmptyState
            title={l.no_derived_facts}
            description={l.no_derived_facts_hint}
            action={
              <Button variant="outline" size="sm" asChild>
                <Link to={workspaceAnalyzeHubPath(workspaceId, 'reasoning')}>
                  {l.open_reasoning}
                </Link>
              </Button>
            }
          />
        ) : (
          <ul className="grid grid-cols-1 gap-3 p-4 md:grid-cols-2">
            {facts.map((fact) => (
              <DerivedFactCard key={fact.id} workspaceId={workspaceId} fact={fact} labels={labels} />
            ))}
          </ul>
        )}
      </DataPanelBody>
    </DataPanel>
  );
}
