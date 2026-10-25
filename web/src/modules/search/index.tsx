import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import {
  DataPanel,
  DataPanelBody,
  DataPanelToolbar,
  EmptyState,
  ToolbarSearch,
} from '@/components/app/shared/console/index.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import {
  SearchChunkList,
  SearchEntityList,
  SearchGraphList,
  type ChunkHit,
  type GraphSearchHit,
} from '@/modules/search/pages/search-results.js';
import { Button } from '@/components/ui/button.js';
import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber, pickCountForm } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { workspaceApiClient } from '@/modules/search/lib/api-client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import type { LedgerEntityHit } from '@/modules/entities/components/ledger-entity-browser.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { graphPath } from '@/modules/graph/lib/graph-url-state.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import {
  searchPath,
  parseSearchUrlState,
  resolveSearchScope,
  type SearchScope,
} from '@/modules/search/lib/search-url-state.js';

const PREVIEW_LIMIT = 8;
const SEARCH_LIMIT = 30;

export function SearchPage() {
  const { t, locale } = useI18n();
  const emptyCell = t.core.common.emptyCell;
  const s = t.search.page;
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();
  const workspaceMeta = id ? getWorkspace(id) : undefined;

  const [scope, setScope] = useState<SearchScope>(() =>
    resolveSearchScope(searchParams.get('scope')),
  );
  const [query, setQuery] = useState(() => searchParams.get('q') ?? '');
  const [asOf, setAsOf] = useState(() => searchParams.get('as_of') ?? '');
  const [at, setAt] = useState(() => searchParams.get('at') ?? '');

  const [graphResults, setGraphResults] = useState<GraphSearchHit[]>([]);
  const [chunkResults, setChunkResults] = useState<ChunkHit[]>([]);
  const [entityResults, setEntityResults] = useState<LedgerEntityHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(() => Boolean(searchParams.get('q')?.trim()));

  const ranUrlQueryKey = useRef<string | null>(null);

  const graphEnabled = !capsLoading && caps?.graph === true;
  const graphScopeBlocked = scope === 'graph' && id && !capsLoading && caps && !caps.graph;

  const graphLabelIds = graphResults.map((hit) => hit.node.id);
  const graphLabels = useWorkspaceNodeLabels(id, graphLabelIds);

  const syncSearchUrl = useCallback(
    (opts: {
      q: string;
      scope: SearchScope;
      asOf?: string;
      at?: string;
    }) => {
      if (!id) return;
      const href = searchPath(id, {
        scope: opts.scope,
        q: opts.q,
        asOf: opts.asOf?.trim() || undefined,
        at: opts.at?.trim() || undefined,
      });
      const next = href.split('?')[1] ?? '';
      setSearchParams(new URLSearchParams(next), { replace: true });
    },
    [id, setSearchParams],
  );

  const fetchChunks = useCallback(
    async (q: string, limit: number, asOfIso: string) => {
      if (!id) return [] as ChunkHit[];
      const trimmed = asOfIso.trim();
      const data = await workspaceApiClient(id).searchChunks(q, limit, {
        ...(trimmed ? { as_of: trimmed } : {}),
      });
      return (data.chunks ?? []) as ChunkHit[];
    },
    [id],
  );

  const fetchGraph = useCallback(
    async (q: string, limit: number, atIso: string) => {
      if (!id) return [] as GraphSearchHit[];
      const trimmed = atIso.trim();
      const data = await workspaceApiClient(id).searchGraph(
        q,
        limit,
        trimmed || undefined,
      );
      return data.results as GraphSearchHit[];
    },
    [id],
  );

  const fetchEntities = useCallback(
    async (q: string, limit: number) => {
      if (!id) return [] as LedgerEntityHit[];
      const client = workspaceApiClient(id);
      if (q.trim()) {
        const data = await client.findEntities(q, limit);
        return (data.ledger_entities ?? []) as LedgerEntityHit[];
      }
      const data = await client.listLedgerEntities(limit);
      return (data.entities ?? []) as LedgerEntityHit[];
    },
    [id],
  );

  const runSearch = useCallback(
    async (
      activeScope: SearchScope,
      q: string,
      temporal: { asOf: string; at: string },
    ) => {
      if (!id) return;
      const trimmed = q.trim();
      const needsQuery = activeScope !== 'entities';
      if (needsQuery && !trimmed) return;

      setLoading(true);
      setError(null);
      setHasSearched(true);

      const limit = SEARCH_LIMIT;

      try {
        if (activeScope === 'chunks') {
          const chunks = await fetchChunks(trimmed, limit, temporal.asOf);
          setChunkResults(chunks);
          setGraphResults([]);
          setEntityResults([]);
        } else if (activeScope === 'graph') {
          if (!graphEnabled) {
            setGraphResults([]);
            setChunkResults([]);
            setEntityResults([]);
            return;
          }
          const graph = await fetchGraph(trimmed, limit, temporal.at);
          setGraphResults(graph);
          setChunkResults([]);
          setEntityResults([]);
        } else {
          const entities = await fetchEntities(trimmed, limit);
          setEntityResults(entities);
          setChunkResults([]);
          setGraphResults([]);
        }
      } catch (err) {
        setError(formatUserFacingApiError(err, locale as Locale));
        setChunkResults([]);
        setGraphResults([]);
        setEntityResults([]);
      } finally {
        setLoading(false);
      }
    },
    [id, fetchChunks, fetchGraph, fetchEntities, graphEnabled, locale],
  );

  useEffect(() => {
    const parsed = parseSearchUrlState(searchParams.toString());
    setScope(parsed.scope);
    const q = searchParams.get('q');
    if (q != null) setQuery(q);
    setAsOf(parsed.asOf ?? '');
    setAt(parsed.at ?? '');
  }, [searchParams]);

  useEffect(() => {
    const q = searchParams.get('q')?.trim();
    if (!q || !id) return;
    const parsed = parseSearchUrlState(searchParams.toString());
    const key = [parsed.scope, q, parsed.asOf ?? '', parsed.at ?? ''].join('|');
    if (ranUrlQueryKey.current === key) return;
    if (parsed.scope === 'graph' && capsLoading) return;
    if (parsed.scope === 'graph' && caps && !caps.graph) {
      ranUrlQueryKey.current = key;
      return;
    }
    ranUrlQueryKey.current = key;
    setQuery(q);
    setScope(parsed.scope);
    void runSearch(parsed.scope, q, {
      asOf: parsed.asOf ?? '',
      at: parsed.at ?? '',
    });
  }, [id, searchParams, capsLoading, caps, runSearch]);

  useEffect(() => {
    if (scope !== 'entities' || !id || hasSearched) return;
    let cancelled = false;
    void fetchEntities('', PREVIEW_LIMIT)
      .then((rows) => {
        if (!cancelled) setEntityResults(rows);
      })
      .catch(() => {
        if (!cancelled) setEntityResults([]);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, id, hasSearched, fetchEntities]);

  function placeholderForScope(activeScope: SearchScope): string {
    if (activeScope === 'chunks') return s.chunk_placeholder;
    if (activeScope === 'graph') return s.graph_placeholder;
    return s.entity_placeholder;
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!id) return;
    if (scope !== 'entities' && !q) return;
    syncSearchUrl({ q, scope, asOf, at });
    void runSearch(scope, q, { asOf, at });
  }

  function changeScope(next: SearchScope) {
    setScope(next);
    syncSearchUrl({ q: query.trim(), scope: next, asOf, at });
    const q = query.trim();
    if (q || next === 'entities') {
      void runSearch(next, q, { asOf, at });
    } else {
      setChunkResults([]);
      setGraphResults([]);
      setEntityResults([]);
      setHasSearched(false);
      setError(null);
    }
  }

  const name = workspaceMeta?.name ?? id ?? t.core.common.ellipsis;

  if (graphScopeBlocked && id) {
    return <WorkspaceUnavailable workspaceId={id} feature="graph" />;
  }

  const resultCount =
    scope === 'chunks'
      ? chunkResults.length
      : scope === 'graph'
        ? graphResults.length
        : entityResults.length;
  const countLabel = fmt(
    pickCountForm(locale, resultCount, s.result_count_one, s.result_count),
    { count: formatLocaleNumber(locale, resultCount) },
  );

  const showTemporal = scope === 'chunks' || scope === 'graph';
  const temporalValue = scope === 'chunks' ? asOf : at;
  const temporalInputId =
    scope === 'chunks' ? 'workspace-search-as-of' : 'workspace-search-at';

  function clearTemporalFilter() {
    if (scope === 'chunks') {
      setAsOf('');
      syncSearchUrl({ q: query.trim(), scope, asOf: '', at });
    } else {
      setAt('');
      syncSearchUrl({ q: query.trim(), scope, asOf, at: '' });
    }
  }

  const resultsBody =
    !id ? (
      <EmptyState title={s.no_results} />
    ) : !hasSearched && !query.trim() && scope !== 'entities' ? (
      <EmptyState title={s.landing_title} description={s.landing_body} />
    ) : scope === 'chunks' ? (
      <SearchChunkList workspaceId={id} hits={chunkResults} copy={s} emptyCell={emptyCell} />
    ) : scope === 'graph' ? (
      <SearchGraphList
        workspaceId={id}
        hits={graphResults}
        labels={graphLabels}
        copy={s}
        locale={locale as Locale}
        graphAt={at}
      />
    ) : (
      <SearchEntityList workspaceId={id} hits={entityResults} copy={s} />
    );

  return (
    <div
      className="basis-search-shell flex min-h-0 w-full flex-1 flex-col"
      data-workspace-id={id ?? undefined}
      data-testid="workspace-search-view"
    >
      <ConsolePageLayout
        crumbs={[
          { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
          { label: name, to: id ? workspacePath(id, 'graph') : '/workspaces' },
          { label: t.search.menu.search },
        ]}
        subtitle={
          <div className="space-y-1">
            <p>
              {t.search.page.subtitle}{' '}
              {id ? (
                <Link
                  to={workspacePath(id, 'settings') + '?tab=search'}
                  className="text-primary underline-offset-2 hover:underline"
                >
                  {s.search_settings_link}
                </Link>
              ) : null}
            </p>
          </div>
        }
        className="gap-6 [&>:last-child]:min-h-0 [&>:last-child]:flex-none"
      >
        <DataPanel data-testid="workspace-search-panel">
          <form onSubmit={onSubmit} className="flex flex-col gap-2">
            <DataPanelToolbar
              className="flex-nowrap"
              search={
                <div
                  className="flex min-w-0 flex-1 flex-nowrap items-center gap-2"
                  data-testid={showTemporal ? 'workspace-search-temporal' : undefined}
                >
                  <ToolbarSearch
                    className="min-w-0 w-full max-w-md flex-1 sm:w-72 sm:flex-none"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={placeholderForScope(scope)}
                    disabled={loading && !hasSearched}
                  />
                  {showTemporal ? (
                    <>
                      <Label htmlFor={temporalInputId} className="sr-only">
                        {scope === 'chunks' ? s.temporal_as_of_label : s.temporal_at_label}
                      </Label>
                      <Input
                        id={temporalInputId}
                        data-testid={temporalInputId}
                        value={temporalValue}
                        onChange={(e) =>
                          scope === 'chunks' ? setAsOf(e.target.value) : setAt(e.target.value)
                        }
                        placeholder="2030-01-01T00:00:00Z"
                        title={s.temporal_hint}
                        className="h-9 w-[10.5rem] shrink-0 font-mono text-xs sm:w-[13rem]"
                        autoComplete="off"
                      />
                      {temporalValue.trim() ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="hidden shrink-0 px-2 sm:inline-flex"
                          onClick={clearTemporalFilter}
                        >
                          {s.clear_temporal}
                        </Button>
                      ) : null}
                    </>
                  ) : null}
                </div>
              }
              actions={
                <div className="flex flex-wrap items-center gap-2">
                  <Label htmlFor="workspace-search-scope" className="sr-only">
                    {s.scope_label}
                  </Label>
                  <Select value={scope} onValueChange={(v) => changeScope(v as SearchScope)}>
                    <SelectTrigger id="workspace-search-scope" className="w-[9.5rem]" size="sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="chunks">{s.scope_documents}</SelectItem>
                      <SelectItem value="graph" disabled={!graphEnabled}>
                        {s.scope_graph}
                      </SelectItem>
                      <SelectItem value="entities">{s.scope_entities}</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button type="submit" size="sm" className="min-w-[5.5rem]" disabled={loading}>
                    {loading ? <Spinner className="size-4" /> : null}
                    {loading ? s.searching : s.search}
                  </Button>
                </div>
              }
            />

            {showTemporal && id && graphEnabled ? (
              <div className="flex flex-wrap items-center gap-1.5">
                {scope === 'graph' ? (
                  <>
                    <Button type="button" variant="outline" size="sm" asChild>
                      <Link
                        to={graphPath(id, { at: at.trim() || undefined })}
                        data-testid="workspace-search-open-graph"
                      >
                        {s.open_graph_link}
                      </Link>
                    </Button>
                    {at.trim() ? (
                      <Button type="button" variant="outline" size="sm" asChild>
                        <Link
                          to={graphPath(id, { at: at.trim(), timeline: true })}
                          data-testid="workspace-search-open-graph-timeline"
                        >
                          {s.open_graph_timeline_link}
                        </Link>
                      </Button>
                    ) : null}
                  </>
                ) : asOf.trim() ? (
                  <Button type="button" variant="outline" size="sm" asChild>
                    <Link
                      to={graphPath(id, { at: asOf.trim(), timeline: true })}
                      data-testid="workspace-search-chunks-open-timeline"
                    >
                      {s.open_graph_timeline_link}
                    </Link>
                  </Button>
                ) : null}
              </div>
            ) : null}
          </form>

          <DataPanelBody padded={false} className="mt-2">
            {error ? (
              <p className="border-b border-border px-4 py-3 text-sm text-destructive">{error}</p>
            ) : null}
            {loading && hasSearched && !error ? (
              <div className="flex justify-center py-16">
                <Spinner className="size-6" />
              </div>
            ) : (
              <>
                {hasSearched && !error ? (
                  <div className="flex items-center justify-between gap-2 border-b border-border/60 px-4 py-2.5">
                    <span className="text-xs font-medium text-foreground">{s.results_title}</span>
                    <span className="text-xs tabular-nums text-muted-foreground">{countLabel}</span>
                  </div>
                ) : null}
                {resultsBody}
              </>
            )}
          </DataPanelBody>
        </DataPanel>
      </ConsolePageLayout>
    </div>
  );
}
