import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { workspacePath } from "@/lib/nav/nav-config.js";
import { cn } from "@/lib/utils.js";
import {
  exWsErrorBanner,
  exWsHint,
  exWsMonoCode,
  exWsMonoMuted,
  exWsScrollFill,
  exWsSkeletonRow,
  exWsSkeletonStack,
  exWsSplitMain,
} from "@/lib/ui-classes/ws-ui.js";
import { fmt, formatLocaleNumber } from "@/i18n/format.js";
import type { LocaleMessages } from "@/i18n/en.js";
import type { Locale } from "@/i18n/locale.js";

type Copy = LocaleMessages['analyze']['reasoning'];

type ReasoningResult = {
  inferred_facts?: string[];
  proof_chains?: Array<{ conclusion: string; rule: string; premises: string[] }>;
  rules_fired?: number;
  added_edges?: number;
  mutated?: boolean;
  derived_facts_persisted?: { created?: number; skipped?: number };
};

function SectionHeading({
  locale,
  title,
  count,
  icon,
}: {
  locale: Locale;
  title: string;
  count?: number;
  icon: string;
}) {
  return (
    <h3 className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
      <PublicIcon name={icon} size={13} />
      {title}
      {typeof count === "number" ? (
        <span className="font-mono text-[11px] tabular-nums text-foreground">
          {formatLocaleNumber(locale, count)}
        </span>
      ) : null}
    </h3>
  );
}

function ResultSection({ children }: { children: ReactNode }) {
  return <section className="flex flex-col">{children}</section>;
}

export function ReasoningResultsPanel({
  locale,
  copy,
  workspaceId,
  result,
  isRunning,
  error,
  resultStale,
  hasInput,
}: {
  locale: Locale;
  copy: Copy;
  workspaceId: string;
  result: ReasoningResult | null;
  isRunning: boolean;
  error: string;
  resultStale: boolean;
  hasInput: boolean;
}) {
  const hasResult = Boolean(result && !isRunning);
  const inferences = result?.inferred_facts ?? [];
  const proofs = result?.proof_chains ?? [];
  const derived = result?.derived_facts_persisted?.created ?? 0;

  return (
    <div className={exWsSplitMain}>
      <div className="flex h-12 shrink-0 items-center gap-4 border-b border-border px-4">
        <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          <PublicIcon name="stars" size={13} />
          {copy.results_title}
        </span>
        {hasResult && result ? (
          <p className="min-w-0 flex-1 truncate text-right font-mono text-[11px] text-muted-foreground">
            {fmt(copy.rules_fired, { n: formatLocaleNumber(locale, result.rules_fired ?? 0) })}
            <span className="mx-1.5 text-border">·</span>
            {fmt(copy.edges_added, { n: formatLocaleNumber(locale, result.added_edges ?? 0) })}
            <span className="mx-1.5 text-border">·</span>
            {result.mutated ? copy.graph_updated : copy.preview_only}
            {derived > 0 ? (
              <>
                <span className="mx-1.5 text-border">·</span>
                <Link
                  to={workspacePath(workspaceId, "entities")}
                  className="text-foreground underline-offset-2 hover:underline"
                >
                  {fmt(copy.derived_link, { n: formatLocaleNumber(locale, derived) })}
                </Link>
              </>
            ) : null}
          </p>
        ) : null}
      </div>

      <div className={cn(exWsScrollFill, "flex flex-col gap-8 px-4 py-4")}>
        {error ? (
          <div className={cn(exWsErrorBanner, "shrink-0")}>
            <PublicIcon name="alert-circle" size={16} className="mt-0.5" />
            <div>{error}</div>
          </div>
        ) : null}

        {isRunning ? (
          <div className={exWsSkeletonStack}>
            {[1, 2, 3].map((i) => <div key={i} className={exWsSkeletonRow} />)}
          </div>
        ) : null}

        {!hasResult && !isRunning && !error ? (
          <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
            <PublicIcon name="list-dashes-01" size={18} className="mb-2 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">{copy.results_empty_title}</p>
            <p className={cn(exWsHint, "mt-1 max-w-xs")}>
              {hasInput ? copy.results_empty_ready : copy.results_empty_body}
            </p>
          </div>
        ) : null}

        {hasResult ? (
          <>
            {resultStale ? (
              <p className={cn(exWsHint, "flex items-center gap-1.5")}>
                <PublicIcon name="clock-backward" size={13} />
                {copy.result_stale}
              </p>
            ) : null}
            <ResultSection>
              <SectionHeading
                locale={locale}
                icon="list-dashes-01"
                title={copy.tab_inferences}
                count={inferences.length}
              />
              {inferences.length === 0 ? (
                <p className={exWsHint}>{copy.complete_empty}</p>
              ) : (
                <ol className="m-0 divide-y divide-border border-y border-border">
                  {inferences.map((fact, i) => (
                    <li key={`${fact}-${i}`} className="flex items-start gap-3 py-2">
                      <span className="w-5 shrink-0 pt-0.5 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                        {i + 1}
                      </span>
                      <code className={exWsMonoCode}>{fact}</code>
                    </li>
                  ))}
                </ol>
              )}
            </ResultSection>

            {proofs.length > 0 ? (
              <ResultSection>
                <SectionHeading locale={locale} icon="path" title={copy.tab_proofs} count={proofs.length} />
                <div className="divide-y divide-border border-y border-border">
                  {proofs.map((chain, i) => (
                    <article key={`${chain.conclusion}-${i}`} className="py-3">
                      <code className={exWsMonoCode}>{chain.conclusion}</code>
                      {chain.premises?.length ? (
                        <ul className="m-0 mt-2 flex list-none flex-col gap-1 border-l border-border p-0 pl-3">
                          {chain.premises.map((premise, j) => (
                            <li key={j} className={exWsMonoMuted}>{premise}</li>
                          ))}
                        </ul>
                      ) : null}
                    </article>
                  ))}
                </div>
              </ResultSection>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
