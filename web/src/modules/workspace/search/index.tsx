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
} from '@/modules/workspace/search/pages/search-results.js';
import { Button } from '@/components/ui/button.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import { Label } from '@/components/ui/label.js';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { DatePicker } from '@/components/app/shared/primitives/date-picker.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber, pickCountForm } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { workspaceApiClient } from '@/modules/workspace/search/lib/api-client.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import type { LedgerEntityHit } from '@/components/app/shared/workspace/ledger-entity-browser.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { graphPath } from '@/modules/workspace/graph/lib/graph-url-state.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import {
  searchPath,
  parseSearchUrlState,
  resolveSearchScope,
  chunkTemporalFromUrlState,
  type SearchScope,
} from '@/modules/workspace/search/lib/search-url-state.js';
import {
  calendarDateFromIso,
  endOfLocalDayIso,
  startOfLocalDayIso,
} from '@/modules/workspace/graph/lib/temporal/day-range.js';
import { parseInstantMs } from '@/modules/workspace/graph/lib/temporal/instant.js';

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
  const initialUrl = parseSearchUrlState(searchParams.toString());
  const initialChunkTemporal = chunkTemporalFromUrlState(initialUrl);
  const [createdAfter, setCreatedAfter] = useState(() => initialChunkTemporal.createdAfter);
  const [createdBefore, setCreatedBefore] = useState(() => initialChunkTemporal.createdBefore);
  const [at, setAt] = useState(() => searchParams.get('at') ?? '');

  const [graphResults, setGraphResults] = useState<GraphSearchHit[]>([]);
  const [chunkResults, setChunkResults] = useState<ChunkHit[]>([]);
  const [entityResults, setEntityResults] = useState<LedgerEntityHit[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(() => Boolean(searchParams.get('q')?.trim()));
  const [includeArchivedGraph, setIncludeArchivedGraph] = useState(
    () => searchParams.get('include_archived') === '1',
  );

  const ranUrlQueryKey = useRef<string | null>(null);

  const graphEnabled = !capsLoading && caps?.graph === true;
  const graphScopeBlocked = scope === 'graph' && id && !capsLoading && caps && !caps.graph;

  const graphLabelIds = graphResults.map((hit) => hit.node.id);
  const graphLabels = useWorkspaceNodeLabels(id, graphLabelIds);

  const syncSearchUrl = useCallback(
    (opts: {
      q: string;
      scope: SearchScope;
      createdAfter?: string;
      createdBefore?: string;
      at?: string;
    }) => {
      if (!id) return;
      const href = searchPath(id, {
        scope: opts.scope,
        q: opts.q,
        createdAfter: opts.createdAfter?.trim() || undefined,
        createdBefore: opts.createdBefore?.trim() || undefined,
        at: opts.at?.trim() || undefined,
      });
      const next = href.split('?')[1] ?? '';
      setSearchParams(new URLSearchParams(next), { replace: true });
    },
    [id, setSearchParams],
  );

  const fetchChunks = useCallback(
    async (q: string, limit: number, range: { createdAfter: string; createdBefore: string }) => {
      if (!id) return [] as ChunkHit[];
      const after = range.createdAfter.trim();
      const before = range.createdBefore.trim();
      const data = await workspaceApiClient(id).searchChunks(q, limit, {
        ...(after ? { created_after: after } : {}),
        ...(before ? { created_before: before } : {}),
      });
      return (data.chunks ?? []) as ChunkHit[];
    },
    [id],
  );

  const fetchGraph = useCallback(
    async (q: string, limit: number, atIso: string, includeArchived: boolean) => {
      if (!id) return [] as GraphSearchHit[];
      const trimmed = atIso.trim();
      const data = await workspaceApiClient(id).searchGraph(q, limit, {
        ...(trimmed ? { at: trimmed } : {}),
        ...(includeArchived ? { include_archived: true } : {}),
      });
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
      temporal: { createdAfter: string; createdBefore: string; at: string },
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
          const chunks = await fetchChunks(trimmed, limit, {
            createdAfter: temporal.createdAfter,
            createdBefore: temporal.createdBefore,
          });
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
          const graph = await fetchGraph(trimmed, limit, temporal.at, includeArchivedGraph);
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
    [id, fetchChunks, fetchGraph, fetchEntities, graphEnabled, includeArchivedGraph, locale],
  );

  useEffect(() => {
    const parsed = parseSearchUrlState(searchParams.toString());
    const chunkTemporal = chunkTemporalFromUrlState(parsed);
    setScope(parsed.scope);
    const q = searchParams.get('q');
    if (q != null) setQuery(q);
    setCreatedAfter(chunkTemporal.createdAfter);
    setCreatedBefore(chunkTemporal.createdBefore);
    setAt(parsed.at ?? '');
  }, [searchParams]);

  useEffect(() => {
    const q = searchParams.get('q')?.trim();
    if (!q || !id) return;
    const parsed = parseSearchUrlState(searchParams.toString());
    const chunkTemporal = chunkTemporalFromUrlState(parsed);
    const key = [
      parsed.scope,
      q,
      chunkTemporal.createdAfter,
      chunkTemporal.createdBefore,
      parsed.at ?? '',
    ].join('|');
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
      createdAfter: chunkTemporal.createdAfter,
      createdBefore: chunkTemporal.createdBefore,
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

  function scopeHint(activeScope: SearchScope): string {
    if (activeScope === 'chunks') return s.scope_documents_hint;
    if (activeScope === 'graph') return s.scope_graph_hint;
    return s.scope_entities_hint;
  }

  function resultCategoryLabel(activeScope: SearchScope): string {
    if (activeScope === 'chunks') return s.result_category_chunk;
    if (activeScope === 'graph') return s.result_category_graph;
    return s.result_category_entity;
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    if (!id) return;
    if (scope !== 'entities' && !q) return;
    syncSearchUrl({ q, scope, createdAfter, createdBefore, at });
    void runSearch(scope, q, { createdAfter, createdBefore, at });
  }

  function changeScope(next: SearchScope) {
    setScope(next);
    syncSearchUrl({ q: query.trim(), scope: next, createdAfter, createdBefore, at });
    const q = query.trim();
    if (q || next === 'entities') {
      void runSearch(next, q, { createdAfter, createdBefore, at });
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
  const chunkFromDay = createdAfter.trim() ? calendarDateFromIso(createdAfter) : undefined;
  const chunkToDay = createdBefore.trim() ? calendarDateFromIso(createdBefore) : undefined;
  const graphAtDay = at.trim() ? calendarDateFromIso(at) : undefined;
  const hasChunkTemporal = Boolean(createdAfter.trim() || createdBefore.trim());
  const hasGraphTemporal = Boolean(at.trim());

  function onSelectChunkFrom(day: Date | undefined) {
    if (!day) return;
    const fromIso = startOfLocalDayIso(day);
    setCreatedAfter(fromIso);
    const toMs = parseInstantMs(createdBefore);
    const fromMs = parseInstantMs(fromIso);
    if (toMs === null || fromMs === null || toMs < fromMs) {
      setCreatedBefore(endOfLocalDayIso(day));
    }
  }

  function onSelectChunkTo(day: Date | undefined) {
    if (!day) return;
    const toIso = endOfLocalDayIso(day);
    const toMs = parseInstantMs(toIso);
    const fromMs = parseInstantMs(createdAfter);
    if (fromMs !== null && toMs !== null && toMs < fromMs) {
      setCreatedAfter(startOfLocalDayIso(day));
    }
    setCreatedBefore(toIso);
  }

  function onSelectGraphAt(day: Date | undefined) {
    if (!day) {
      setAt('');
      return;
    }
    setAt(endOfLocalDayIso(day));
  }

  function clearTemporalFilter() {
    if (scope === 'chunks') {
      setCreatedAfter('');
      setCreatedBefore('');
      syncSearchUrl({ q: query.trim(), scope, createdAfter: '', createdBefore: '', at });
    } else {
      setAt('');
      syncSearchUrl({ q: query.trim(), scope, createdAfter, createdBefore, at: '' });
    }
  }

  const resultsBody =
    !id ? (
      <EmptyState title={s.no_results} />
    ) : !hasSearched && !query.trim() && scope !== 'entities' ? (
      <EmptyState title={s.landing_title} description={scopeHint(scope)} />
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
          <form onSubmit={onSubmit}>
            <DataPanelToolbar
              className="flex-wrap gap-y-2"
              search={
                <div className="flex flex-wrap items-center gap-2">
                  <Tabs value={scope} onValueChange={(v) => changeScope(v as SearchScope)}>
                    <TabsList id="workspace-search-scope" aria-label={s.scope_label}>
                      <TabsTrigger value="chunks" className="px-3 text-xs">
                        {s.scope_documents}
                      </TabsTrigger>
                      <TabsTrigger
                        value="graph"
                        disabled={!graphEnabled}
                        className="px-3 text-xs"
                      >
                        {s.scope_graph}
                      </TabsTrigger>
                      <TabsTrigger value="entities" className="px-3 text-xs">
                        {s.scope_entities}
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>

                  {scope === 'graph' && id && graphEnabled ? (
                    <>
                      <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                        <Checkbox
                          id="search-include-archived-graph"
                          checked={includeArchivedGraph}
                          onCheckedChange={(checked) => {
                            setIncludeArchivedGraph(checked === true);
                          }}
                        />
                        {s.include_archived_graph}
                      </label>
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
                  ) : scope === 'chunks' && id && graphEnabled && createdBefore.trim() ? (
                    <Button type="button" variant="outline" size="sm" asChild>
                      <Link
                        to={graphPath(id, { at: createdBefore.trim(), timeline: true })}
                        data-testid="workspace-search-chunks-open-timeline"
                      >
                        {s.open_graph_timeline_link}
                      </Link>
                    </Button>
                  ) : null}
                </div>
              }
              actions={
                <div
                  className="flex flex-wrap items-center justify-end gap-2"
                  data-testid={showTemporal ? 'workspace-search-temporal' : undefined}
                >
                  {scope === 'chunks' ? (
                    <div className="flex items-center gap-1.5" role="group" aria-label={s.temporal_as_of_label}>
                      <Label htmlFor="workspace-search-created-after" className="sr-only">
                        {s.temporal_from_label}
                      </Label>
                      <DatePicker
                        id="workspace-search-created-after"
                        testId="workspace-search-created-after"
                        value={chunkFromDay}
                        placeholder={s.temporal_from_placeholder}
                        className="h-9 w-[8.25rem] shrink-0 text-xs"
                        onChange={onSelectChunkFrom}
                      />
                      <span className="text-xs text-muted-foreground" aria-hidden>
                        –
                      </span>
                      <Label htmlFor="workspace-search-created-before" className="sr-only">
                        {s.temporal_to_label}
                      </Label>
                      <DatePicker
                        id="workspace-search-created-before"
                        testId="workspace-search-created-before"
                        value={chunkToDay}
                        placeholder={s.temporal_to_placeholder}
                        className="h-9 w-[8.25rem] shrink-0 text-xs"
                        onChange={onSelectChunkTo}
                      />
                      {hasChunkTemporal ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 shrink-0 px-2 text-xs text-muted-foreground"
                          onClick={clearTemporalFilter}
                        >
                          {s.clear_temporal}
                        </Button>
                      ) : null}
                    </div>
                  ) : scope === 'graph' ? (
                    <div className="flex items-center gap-1.5" role="group" aria-label={s.temporal_at_label}>
                      <Label htmlFor="workspace-search-at" className="sr-only">
                        {s.temporal_at_label}
                      </Label>
                      <DatePicker
                        id="workspace-search-at"
                        testId="workspace-search-at"
                        value={graphAtDay}
                        placeholder={s.temporal_at_placeholder}
                        className="h-9 w-[8.75rem] shrink-0 text-xs"
                        onChange={onSelectGraphAt}
                      />
                      {hasGraphTemporal ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-8 shrink-0 px-2 text-xs text-muted-foreground"
                          onClick={clearTemporalFilter}
                        >
                          {s.clear_temporal}
                        </Button>
                      ) : null}
                    </div>
                  ) : null}

                  <ToolbarSearch
                    className="min-w-[14rem] flex-1 sm:w-64 sm:flex-none md:w-72"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder={placeholderForScope(scope)}
                    disabled={loading && !hasSearched}
                  />

                  <Button type="submit" size="sm" className="min-w-[5rem]" disabled={loading}>
                    {loading ? <Spinner className="size-4" /> : null}
                    {loading ? s.searching : s.search}
                  </Button>
                </div>
              }
            />
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
                {(hasSearched || (scope === 'entities' && entityResults.length > 0)) && !error ? (
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-4 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-foreground">
                        {resultCategoryLabel(scope)}
                      </span>
                      {scope === 'entities' && !hasSearched && !query.trim() ? (
                        <span className="text-xs text-muted-foreground">
                          · {s.entity_preview_hint}
                        </span>
                      ) : null}
                    </div>
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
