import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState } from '@/components/app/shared/console/index.js';
import {
  ledgerEntityId,
  type LedgerEntityHit,
} from '@/components/app/shared/workspace/ledger-entity-browser.js';
import { fmt, formatLocaleFixedDecimals } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import type { LocaleMessages } from '@/i18n/en.js';
import { formatNodeRefDetail } from '@/lib/workspace/format-node-ref.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { graphPath } from '@/modules/graph/lib/graph-url-state.js';
import { graphNodeTypeLabel } from '@/modules/graph/i18n/screen-copy.js';

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
  'text-[15px] leading-snug text-primary underline-offset-2 hover:underline';

const metaLineClass = 'mt-0.5 text-xs leading-snug text-muted-foreground';

const snippetClass = 'mt-1 text-sm leading-relaxed text-foreground/85 line-clamp-3';

const secondaryLinkClass =
  'mt-1.5 inline-block text-xs text-muted-foreground underline-offset-2 hover:text-primary hover:underline';

function SearchResultList({ children }: { children: ReactNode }) {
  return <ul className="divide-y divide-border/60">{children}</ul>;
}

function SearchResultItem({ children }: { children: ReactNode }) {
  return <li className="px-4 py-3.5 first:pt-4 last:pb-4">{children}</li>;
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
        <SearchResultItem key={hit.chunk_id}>
          <Link to={evidenceHref(hit.chunk_id)} className={titleLinkClass}>
            {hit.document_title || hit.document_id}
          </Link>
          <p className={metaLineClass}>
            {fmt(copy.chunk_meta, { ordinal: hit.ordinal, chunkId: hit.chunk_id })}
          </p>
          {hit.snippet ? (
            <p className={snippetClass}>{hit.snippet}</p>
          ) : (
            <p className={`${snippetClass} text-muted-foreground`}>{emptyCell}</p>
          )}
          <Link to={evidenceHref(hit.chunk_id)} className={secondaryLinkClass}>
            {copy.evidence}
          </Link>
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
          <SearchResultItem key={hit.node.id}>
            <Link to={graphHref} className={titleLinkClass}>
              {title}
            </Link>
            <p className={metaLineClass}>
              {subtitle ? `${subtitle} · ` : null}
              {fmt(copy.graph_score_line, { type: typeLabel, score: scoreLabel })}
            </p>
            {showContent ? <p className={snippetClass}>{hit.node.content}</p> : null}
            <Link to={graphHref} className={secondaryLinkClass}>
              {copy.open_in_graph}
            </Link>
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
          <SearchResultItem key={entityId}>
            <Link to={graphHref} className={titleLinkClass}>
              {title}
            </Link>
            {subtitle || hit.entity_kind ? (
              <p className={metaLineClass}>
                {subtitle ?? null}
                {subtitle && hit.entity_kind ? ' · ' : null}
                {hit.entity_kind ?? null}
              </p>
            ) : null}
            {hit.description ? <p className={snippetClass}>{hit.description}</p> : null}
            <Link to={graphHref} className={secondaryLinkClass}>
              {copy.open_in_graph}
            </Link>
          </SearchResultItem>
        );
      })}
    </SearchResultList>
  );
}
