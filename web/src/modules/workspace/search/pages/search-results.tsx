import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '@/components/app/shared/console/index.js';
import { Badge } from '@/components/ui/badge.js';
import {
  ledgerEntityId,
  type LedgerEntityHit,
} from '@/components/app/shared/workspace/ledger-entity-browser.js';
import { fmt, formatLocaleFixedDecimals } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import type { LocaleMessages } from '@/i18n/en.js';
import { formatNodeRefDetail } from '@/lib/workspace/format-node-ref.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { graphPath } from '@/modules/workspace/graph/lib/graph-url-state.js';
import { graphNodeTypeLabel } from '@/modules/workspace/graph/i18n/screen-copy.js';

export type GraphSearchHit = {
  node: { id: string; type: string; content: string };
  score: number;
};

export type ChunkHit = {
  chunk_id: string;
  document_id: string;
  document_title: string;
  snippet: string;
  ordinal: number;
};

type SearchPageCopy = LocaleMessages['search']['page'];

const titleLinkClass =
  'text-sm leading-snug text-foreground underline-offset-2 hover:text-primary hover:underline';

const actionLinkClass =
  'shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-primary hover:underline';

function SearchResultList({ children }: { children: ReactNode }) {
  return <ul className="divide-y divide-border/60">{children}</ul>;
}

function SearchResultItem({
  category,
  children,
}: {
  category: 'chunk' | 'graph' | 'entity';
  children: ReactNode;
}) {
  return (
    <li
      data-result-category={category}
      className="px-4 py-3.5 transition-colors hover:bg-muted/20"
    >
      {children}
    </li>
  );
}

export function SearchChunkList({
  workspaceId,
  hits,
  copy,
  emptyCell,
}: {
  workspaceId: string;
  hits: ChunkHit[];
  copy: SearchPageCopy;
  emptyCell: string;
}) {
  if (hits.length === 0) {
    return <EmptyState title={copy.no_results} />;
  }
  const evidenceHref = (chunkId: string) =>
    `${workspacePath(workspaceId, 'sources')}?chunk=${encodeURIComponent(chunkId)}`;

  return (
    <SearchResultList>
      {hits.map((hit) => (
        <SearchResultItem key={hit.chunk_id} category="chunk">
          <div className="flex items-baseline justify-between gap-3">
            <div className="flex min-w-0 flex-wrap items-baseline gap-2">
              <Link to={evidenceHref(hit.chunk_id)} className={titleLinkClass}>
                {hit.document_title || hit.document_id}
              </Link>
              <span
                className="font-mono text-xs tabular-nums text-muted-foreground"
                title={fmt(copy.chunk_meta, { ordinal: hit.ordinal, chunkId: hit.chunk_id })}
              >
                {fmt(copy.chunk_ordinal_badge, { ordinal: hit.ordinal })}
              </span>
            </div>
            <Link to={evidenceHref(hit.chunk_id)} className={actionLinkClass}>
              {copy.evidence}
            </Link>
          </div>
          {hit.snippet ? (
            <blockquote className="mt-2 border-l-2 border-border pl-3 text-sm leading-relaxed text-muted-foreground line-clamp-3">
              {hit.snippet}
            </blockquote>
          ) : (
            <p className="mt-1.5 text-sm text-muted-foreground">{emptyCell}</p>
          )}
        </SearchResultItem>
      ))}
    </SearchResultList>
  );
}

export function SearchGraphList({
  workspaceId,
  hits,
  labels,
  copy,
  locale,
  graphAt,
}: {
  workspaceId: string;
  hits: GraphSearchHit[];
  labels: Record<string, string | null>;
  copy: SearchPageCopy;
  locale: Locale;
  /** Pass search page `at` into graph deep links (F-SRCH-03). */
  graphAt?: string;
}) {
  if (hits.length === 0) {
    return <EmptyState title={copy.no_results} />;
  }
  return (
    <SearchResultList>
      {hits.map((hit) => {
        const { title, subtitle } = formatNodeRefDetail(hit.node.id, labels);
        const typeLabel = graphNodeTypeLabel(locale, hit.node.type);
        const scoreLabel = formatLocaleFixedDecimals(locale, hit.score, 3);
        const graphHref = graphPath(workspaceId, {
          focus: hit.node.id,
          ...(graphAt?.trim() ? { at: graphAt.trim() } : {}),
        });
        const showContent =
          hit.node.content && hit.node.content !== labels[hit.node.id];
        return (
          <SearchResultItem key={hit.node.id} category="graph">
            <div className="flex items-baseline justify-between gap-3">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <Badge variant="outline" className="text-[11px] font-normal">
                  {typeLabel}
                </Badge>
                <Link to={graphHref} className={titleLinkClass}>
                  {title}
                </Link>
                {subtitle ? (
                  <span
                    className="max-w-[14rem] truncate font-mono text-xs text-muted-foreground"
                    title={subtitle}
                  >
                    {subtitle}
                  </span>
                ) : null}
              </div>
              <div className="flex shrink-0 items-baseline gap-3">
                <span
                  className="font-mono text-xs tabular-nums text-muted-foreground"
                  title={fmt(copy.graph_score_line, { type: typeLabel, score: scoreLabel })}
                >
                  {fmt(copy.score_badge, { score: scoreLabel })}
                </span>
                <Link to={graphHref} className={actionLinkClass}>
                  {copy.open_in_graph}
                </Link>
              </div>
            </div>
            {showContent ? (
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground line-clamp-2">
                {hit.node.content}
              </p>
            ) : null}
          </SearchResultItem>
        );
      })}
    </SearchResultList>
  );
}

export function SearchEntityList({
  workspaceId,
  hits,
  copy,
}: {
  workspaceId: string;
  hits: LedgerEntityHit[];
  copy: SearchPageCopy;
}) {
  if (hits.length === 0) {
    return <EmptyState title={copy.no_results} />;
  }
  return (
    <SearchResultList>
      {hits.map((hit) => {
        const entityId = ledgerEntityId(hit);
        const labels: Record<string, string | null> = {
          [entityId]: hit.canonical_label,
        };
        const { title, subtitle } = formatNodeRefDetail(entityId, labels);
        const graphHref = graphPath(workspaceId, { focus: entityId });
        return (
          <SearchResultItem key={entityId} category="entity">
            <div className="flex items-baseline justify-between gap-3">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <Link to={graphHref} className={titleLinkClass}>
                  {title}
                </Link>
                {hit.entity_kind ? (
                  <Badge variant="secondary" className="text-[11px] font-normal">
                    {hit.entity_kind}
                  </Badge>
                ) : null}
              </div>
              <Link to={graphHref} className={actionLinkClass}>
                {copy.open_in_graph}
              </Link>
            </div>
            {hit.description ? (
              <p className="mt-1 text-sm leading-relaxed text-muted-foreground line-clamp-2">
                {hit.description}
              </p>
            ) : subtitle ? (
              <p className="mt-1 font-mono text-xs text-muted-foreground">{subtitle}</p>
            ) : null}
          </SearchResultItem>
        );
      })}
    </SearchResultList>
  );
}
