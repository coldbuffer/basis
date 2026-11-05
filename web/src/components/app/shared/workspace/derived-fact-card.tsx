import { Link } from 'react-router-dom';
import { EntityRefLine } from '@/components/app/shared/workspace/entity-ref-line.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Badge } from '@/components/ui/badge.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleDateTime, pickCountForm } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { hrefForDerivedFactPremise } from '@/modules/workspace/entities/lib/derived-fact-premise-link.js';
import { graphPath } from '@/modules/workspace/graph/lib/graph-url-state.js';

export type DerivedFactView = {
  id: string;
  subject_id: string;
  predicate_uri: string;
  object_entity_id: string | null;
  object_value: string | null;
  recorded_at?: string | null;
  derivations: Array<{ premise_kind?: string; premise_id?: string }>;
};

export function predicateShortLabel(uri: string): string {
  const trimmed = uri.replace(/[#/]+$/, '');
  const cut = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('#'));
  const label = (cut >= 0 ? trimmed.slice(cut + 1) : trimmed).replace(/[_-]+/g, ' ');
  return label || uri;
}

export function DerivedFactCard({
  workspaceId,
  fact,
  labels,
}: {
  workspaceId: string;
  fact: DerivedFactView;
  labels: Record<string, string | null | undefined>;
}) {
  const { locale, t } = useI18n();
  const l = t.entities.ledger;
  const emptyCell = t.core.common.emptyCell;
  const when = fact.recorded_at
    ? formatLocaleDateTime(locale as Locale, fact.recorded_at, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }) || null
    : null;
  const premiseCount = fact.derivations.length;
  const premiseBadgeLabel = fmt(
    pickCountForm(locale, premiseCount, l.premise_count_one, l.premise_count),
    { count: premiseCount },
  );

  return (
    <li className="rounded-lg border border-border/70 bg-muted/15 px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <Badge
          variant="outline"
          className="max-w-full truncate font-mono text-[11px] font-normal"
          title={fact.predicate_uri}
        >
          {predicateShortLabel(fact.predicate_uri)}
        </Badge>
        {when ? (
          <time className="shrink-0 text-[11px] tabular-nums text-muted-foreground">{when}</time>
        ) : null}
      </div>

      <div className="mt-2 flex flex-wrap items-baseline gap-x-1.5 gap-y-1 text-sm">
        <Link
          to={graphPath(workspaceId, { focus: fact.subject_id })}
          className="min-w-0 rounded-sm underline-offset-2 hover:text-primary hover:underline"
        >
          <EntityRefLine id={fact.subject_id} labels={labels} />
        </Link>
        <PublicIcon name="arrow-right" size={13} className="shrink-0 text-muted-foreground" />
        <div className="min-w-0">
          {fact.object_entity_id ? (
            <Link
              to={graphPath(workspaceId, { focus: fact.object_entity_id })}
              className="rounded-sm underline-offset-2 hover:text-primary hover:underline"
            >
              <EntityRefLine id={fact.object_entity_id} labels={labels} />
            </Link>
          ) : (
            <span className="text-sm text-foreground">{fact.object_value || emptyCell}</span>
          )}
        </div>
      </div>

      {premiseCount > 0 ? (
        <details className="group mt-2 border-t border-border/50 pt-1.5">
          <summary className="flex cursor-pointer list-none items-center justify-between text-[11px] text-muted-foreground hover:text-foreground [&::-webkit-details-marker]:hidden">
            <span>
              {l.premises_label} · {premiseBadgeLabel}
            </span>
            <PublicIcon
              name="chevron-down"
              size={12}
              className="transition-transform group-open:rotate-180"
            />
          </summary>
          <ul className="mt-1.5 space-y-1" data-testid="derived-fact-premises">
            {fact.derivations.map((premise, index) => {
              const href = hrefForDerivedFactPremise(workspaceId, premise);
              const label = premise.premise_id ?? emptyCell;
              return (
                <li
                  key={`${premise.premise_id ?? index}-${index}`}
                  className="truncate font-mono text-[11px] text-muted-foreground"
                  data-testid="derived-fact-premise-row"
                  title={label}
                >
                  {premise.premise_kind ? (
                    <span className="text-foreground/80">{premise.premise_kind}: </span>
                  ) : null}
                  {href ? (
                    <Link
                      to={href}
                      className="text-foreground underline-offset-2 hover:text-primary hover:underline"
                      data-testid="derived-fact-premise-link"
                    >
                      {label}
                    </Link>
                  ) : (
                    label
                  )}
                </li>
              );
            })}
          </ul>
        </details>
      ) : null}
    </li>
  );
}
