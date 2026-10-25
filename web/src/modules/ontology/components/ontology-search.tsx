import { Button } from "@/components/ui/button.js";
import { Input } from "@/components/ui/input.js";
import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useEffect, useRef, useState } from "react";
import { wsApiErrorMessage, wsGetJson, parseWsJson } from '@/lib/workspace/ws-api-error';
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { ontologyApiSuffix, useOntologyWorkspaceId } from "./ontology-workspace-context";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleNumber, pickCountForm } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { cn } from "@/lib/utils.js";
import {
  ontBadgeBase,
  ontEntityTypeBadgeClass,
  ontEntityTypeBadgeFallback,
  ontManagerCloseBtn,
  ontSearchBar,
  ontSearchBody,
  ontSearchClearBtn,
  ontSearchCollapseBtn,
  ontSearchDetailBody,
  ontSearchDetailHeader,
  ontSearchDetailPanel,
  ontSearchDetailSection,
  ontSearchDetailSectionLabel,
  ontSearchFilterActive,
  ontSearchFilterBtn,
  ontSearchFilterIdle,
  ontSearchHint,
  ontSearchInput,
  ontSearchOpenUri,
  ontSearchResultIdle,
  ontSearchResultList,
  ontSearchResultRow,
  ontSearchResultSelected,
  ontSearchResults,
  ontSearchShell,
  ontSearchTop,
} from "@/lib/ui-classes/ontology-ui.js";

interface SearchResult {
  uri: string;
  label: string;
  type: string;
  entity_type: string;
  definition?: string;
  source_ontology?: string;
  namespace_prefix?: string;
}

interface EntityDetail {
  uri: string;
  label: string;
  type: string;
  entity_type: string;
  definition?: string;
  source_ontology?: string;
  superclasses: string[];
  subclasses: string[];
  domain: string[];
  range: string[];
  instance_count: number;
  properties: Record<string, unknown>;
}

function TypeBadge({ entityType }: { entityType: string }) {
  const { t } = useI18n();
  const types = t.ontology.hub.search.entity_types;
  const label =
    types[entityType as keyof typeof types] ?? types.unknown ?? entityType;
  return (
    <span
      className={cn(
        ontBadgeBase,
        "shrink-0",
        ontEntityTypeBadgeClass[entityType] ?? ontEntityTypeBadgeFallback,
      )}
    >
      {label}
    </span>
  );
}

function UriRef({ uri }: { uri: string }) {
  const short = uri.includes("#")
    ? uri.split("#").pop() || uri
    : uri.split("/").pop() || uri;
  return (
    <span
      title={uri}
      className="cursor-help font-mono text-[11px] text-primary"
    >
      {short}
    </span>
  );
}

function ResultRow({
  result,
  selected,
  onSelect,
}: {
  result: SearchResult;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useI18n();
  const s = t.ontology.hub.search;
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onSelect();
      }}
      className={cn(
        ontSearchResultRow,
        selected ? ontSearchResultSelected : ontSearchResultIdle,
      )}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm font-bold text-foreground">
          {result.label || result.uri}
        </span>
        <TypeBadge entityType={result.entity_type} />
      </div>
      <div className="truncate font-mono text-[10px] text-muted-foreground">
        {result.uri}
      </div>
      {result.definition ? (
        <div className="line-clamp-2 text-xs leading-snug text-muted-foreground">
          {result.definition}
        </div>
      ) : null}
      {result.source_ontology ? (
        <div className="text-[10px] text-muted-foreground/80">
          {fmt(s.from_source, { source: result.source_ontology })}
        </div>
      ) : null}
    </div>
  );
}

function CollapsibleList({ label, items }: { label: string; items: string[] }) {
  const { t, locale } = useI18n();
  const s = t.ontology.hub.search;
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  return (
    <div>
      <Button
        type="button"
        variant="ghost"
        className={cn(ontSearchCollapseBtn, "h-auto justify-start px-0 font-normal")}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <PublicIcon name="chevron-down" size={12} /> : <PublicIcon name="chevron-right" size={12} />}
        <span>{label}</span>
        <span className="text-[10px]">({formatLocaleNumber(locale, items.length)})</span>
      </Button>
      {open ? (
        <div className="ml-4 mt-1 flex flex-col gap-1">
          {items.slice(0, 12).map((uri) => (
            <div key={uri} className="flex items-center gap-1.5">
              <span className="text-[10px] text-muted-foreground">→</span>
              <UriRef uri={uri} />
            </div>
          ))}
          {items.length > 12 ? (
            <span className="text-[10px] text-muted-foreground">
              {fmt(s.more_items, { count: formatLocaleNumber(locale, items.length - 12) })}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function DetailPanel({
  uri,
  onClose,
}: {
  uri: string;
  onClose: () => void;
}) {
  const { t, locale } = useI18n();
  const s = t.ontology.hub.search;
  const workspaceId = useOntologyWorkspaceId();
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [prevUri, setPrevUri] = useState(uri);
  if (uri !== prevUri) {
    setPrevUri(uri);
    setLoading(true);
    setError("");
    setDetail(null);
  }

  useEffect(() => {
    let ignore = false;
    void wsGetJson<EntityDetail>(
      workspaceId,
      ontologyApiSuffix(`entity/${encodeURIComponent(uri)}`),
      {
        fallbackMessage: s.api.entity_not_found,
        partialWarning: s.api.partial_entity,
        locale: locale as Locale,
      },
    )
      .then(({ data, partialWarning }) => {
        if (ignore) return;
        if (partialWarning) setError(partialWarning);
        setDetail(data);
      })
      .catch((e) => {
        if (!ignore) setError(wsApiErrorMessage(e, locale as Locale));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => { ignore = true; };
  }, [workspaceId, locale, s.api.entity_not_found, s.api.partial_entity, uri]);

  return (
    <div className={ontSearchDetailPanel}>
      <div className={ontSearchDetailHeader}>
        <div className="flex min-w-0 items-center gap-2">
          <PublicIcon name="book-01" size={14} className="shrink-0 text-primary" />
          <span className="truncate text-sm font-bold text-foreground">{s.entity_detail}</span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className={ontManagerCloseBtn}
          onClick={onClose}
          aria-label={s.close_aria}
        >
          <PublicIcon name="x-02" size={14} />
        </Button>
      </div>

      {loading ? (
        <div className={ontSearchHint}>
          <PublicIcon name="loader-01" size={18} className="animate-spin text-primary" />
        </div>
      ) : null}

      {error && !loading ? (
        <div className={cn(ontSearchHint, "text-center")}>
          <PublicIcon name="alert-circle" size={16} className="text-destructive" />
          <span className="mt-1.5 text-xs text-destructive">{error}</span>
        </div>
      ) : null}

      {detail && !loading ? (
        <div className={ontSearchDetailBody}>
          <div className="mb-3.5">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <h3 className="m-0 text-lg font-extrabold tracking-tight text-foreground">
                {detail.label || detail.uri.split("/").pop()}
              </h3>
              <TypeBadge entityType={detail.entity_type} />
            </div>
            <div className="break-all font-mono text-[10px] text-muted-foreground">
              {detail.uri}
            </div>
          </div>

          {detail.definition ? (
            <DetailSection label={s.definition}>
              <p className="m-0 text-sm leading-relaxed text-muted-foreground">
                {detail.definition}
              </p>
            </DetailSection>
          ) : null}

          {detail.instance_count > 0 ? (
            <DetailSection label={s.instances}>
              <span className="text-sm font-extrabold text-ok">
                {formatLocaleNumber(locale, detail.instance_count)}
              </span>
            </DetailSection>
          ) : null}

          <CollapsibleList label={s.superclasses} items={detail.superclasses} />
          <CollapsibleList label={s.subclasses} items={detail.subclasses} />
          <CollapsibleList label={s.domain} items={detail.domain} />
          <CollapsibleList label={s.range} items={detail.range} />

          {detail.source_ontology ? (
            <DetailSection label={s.source_ontology}>
              <span className="font-mono text-xs text-muted-foreground">
                {detail.source_ontology}
              </span>
            </DetailSection>
          ) : null}

          <a
            href={detail.uri}
            target="_blank"
            rel="noreferrer"
            className={ontSearchOpenUri}
          >
            <PublicIcon name="link-external" size={11} />
            {s.open_uri}
          </a>
        </div>
      ) : null}
    </div>
  );
}

function DetailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={ontSearchDetailSection}>
      <div className={ontSearchDetailSectionLabel}>{label}</div>
      {children}
    </div>
  );
}

export function OntologySearch() {
  const { t, locale } = useI18n();
  const s = t.ontology.hub.search;
  const workspaceId = useOntologyWorkspaceId();
  const [query, setQuery] = useState("");
  const [entityType, setEntityType] = useState<string>("all");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedUri, setSelectedUri] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runSearch = async (q: string, type: string) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const query: Record<string, string> = { q: q.trim(), limit: "80" };
      if (type !== "all") query.entity_type = type;
      const res = await workspaceOpenApiResponse('GET', workspaceId, ontologyApiSuffix("search"), {
        params: { query },
      });
      setResults(await parseWsJson<SearchResult[]>(res, s.api.search_failed));
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => runSearch(query, entityType), 320);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [entityType, workspaceId, query, s.api.search_failed]);

  const filterTypes = ["all", "class", "property", "individual", "concept", "scheme"] as const;

  return (
    <div className={ontSearchShell}>
      <div className={ontSearchTop}>
        <div className={ontSearchBar}>
          <PublicIcon name="search-01" size={14} className="shrink-0 text-muted-foreground" />
          <Input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={s.placeholder}
            className={cn(ontSearchInput, "h-8 border-0 bg-transparent shadow-none focus-visible:ring-0")}
          />
          {searching ? (
            <PublicIcon name="loader-01" size={13} className="shrink-0 animate-spin text-primary" />
          ) : null}
          {query && !searching ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={() => { setQuery(""); setResults([]); }}
              className={ontSearchClearBtn}
              aria-label={s.clear_aria}
            >
              <PublicIcon name="x-02" size={12} />
            </Button>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-1">
          {filterTypes.map((ft) => (
            <Button
              key={ft}
              type="button"
              variant="ghost"
              onClick={() => setEntityType(ft)}
              className={cn(
                ontSearchFilterBtn,
                "h-auto font-normal",
                entityType === ft ? ontSearchFilterActive : ontSearchFilterIdle,
              )}
            >
              {s.entity_types[ft]}
            </Button>
          ))}
        </div>
      </div>

      <div className={ontSearchBody}>
        <div className={ontSearchResults}>
          {!query ? (
            <div className={ontSearchHint}>
              <PublicIcon name="search-01" size={20} className="text-primary/20" />
              <span className="mt-2 text-xs text-muted-foreground">{s.hint}</span>
            </div>
          ) : null}

          {query && results.length === 0 && !searching ? (
            <div className={ontSearchHint}>
              <span className="text-xs text-muted-foreground">
                {fmt(s.no_results_for, { query })}
              </span>
            </div>
          ) : null}

          {results.length > 0 ? (
            <div className={ontSearchResultList}>
              <div className="mb-0.5 text-[11px] font-bold text-muted-foreground">
                {fmt(pickCountForm(locale, results.length, s.result_count_one, s.result_count), {
                  count: formatLocaleNumber(locale, results.length),
                })}
              </div>
              {results.map((r) => (
                <ResultRow
                  key={r.uri}
                  result={r}
                  selected={selectedUri === r.uri}
                  onSelect={() => setSelectedUri((prev) => (prev === r.uri ? null : r.uri))}
                />
              ))}
            </div>
          ) : null}
        </div>

        {selectedUri ? (
          <DetailPanel uri={selectedUri} onClose={() => setSelectedUri(null)} />
        ) : null}
      </div>
    </div>
  );
}
