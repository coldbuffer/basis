import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  DataPanel,
  DataPanelBody,
  DataPanelHeader,
  DataPanelTableFooter,
  ToolbarSearch,
} from '@/components/app/shared/console/index.js';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import { Label } from '@/components/ui/label.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Switch } from '@/components/ui/switch.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import { downloadTextBlob } from '@/lib/admin/download-text-blob.js';
import { rowsToCsv } from '@/lib/admin/csv.js';
import { parsePlatformAllowlistFile } from '@/modules/admin/connectors/lib/platform-connector-allowlist-import.js';
import { openApiGET, openApiPOST, openApiPUT } from '@/lib/openapi/client.js';
import { resourceCardSurfaceClass } from '@/lib/ui-classes/card-surface.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { PlatformConnectorCategoryBreakdown } from '@/modules/admin/connectors/components/platform-connector-category-breakdown.js';
import { PlatformConnectorManifestDialog } from '@/modules/admin/connectors/components/platform-connector-manifest-dialog.js';
import { cn } from '@/lib/utils.js';

type CatalogStats = {
  providers: number;
  providers_with_streams: number;
  total_streams: number;
  total_tools: number;
};

type CatalogRow = {
  service: string;
  display_name: string;
  description?: string;
  categories: string[];
  auth_modes: string[];
  stream_count: number;
  tool_count: number;
  platform_enabled: boolean;
};

type CatalogResponse = {
  stats: CatalogStats;
  allowed_providers: string[] | string;
  enabled_provider_count: number;
  restrict_mode: boolean;
  categories: string[];
  total_matched: number;
  offset: number;
  limit: number;
  connectors: CatalogRow[];
};

const PAGE_SIZE = 100;

function setsEqual(a: Set<string>, b: Set<string>): boolean {
  if (a.size !== b.size) return false;
  for (const v of a) {
    if (!b.has(v)) return false;
  }
  return true;
}

function allowlistFromDraft(allowAll: boolean, enabled: Set<string>): string[] | string {
  if (allowAll) return '*';
  return [...enabled].sort();
}

export function PlatformConnectorAdmin() {
  const { t, locale } = useI18n();
  const ps = t.admin_settings.page.connectors;
  const formatApiError = useApiErrorMessage();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState<CatalogStats | null>(null);
  const [enabledCount, setEnabledCount] = useState(0);

  const [allowAll, setAllowAll] = useState(true);
  const [savedAllowAll, setSavedAllowAll] = useState(true);
  const [enabledServices, setEnabledServices] = useState<Set<string>>(() => new Set());
  const [savedEnabledServices, setSavedEnabledServices] = useState<Set<string>>(() => new Set());

  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [category, setCategory] = useState<string>('__all__');
  const [streamsOnly, setStreamsOnly] = useState(false);
  const [offset, setOffset] = useState(0);

  const [categories, setCategories] = useState<string[]>([]);
  const [rows, setRows] = useState<CatalogRow[]>([]);
  const [totalMatched, setTotalMatched] = useState(0);
  const [categoryBreakdown, setCategoryBreakdown] = useState<
    { category: string; total: number; enabled: number }[]
  >([]);
  const [detailService, setDetailService] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const importInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQuery(searchQuery.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    setOffset(0);
  }, [debouncedQuery, category, streamsOnly]);

  const dirty = useMemo(() => {
    if (allowAll !== savedAllowAll) return true;
    if (allowAll) return false;
    return !setsEqual(enabledServices, savedEnabledServices);
  }, [allowAll, savedAllowAll, enabledServices, savedEnabledServices]);

  const loadSummary = useCallback(async () => {
    const body = await openApiGET<{
      allowed_providers: string[] | string;
      stats: CatalogStats;
      enabled_provider_count: number;
      restrict_mode: boolean;
    }>('/api/v1/settings/connectors');
    setStats(body.stats);
    setEnabledCount(body.enabled_provider_count);
    const restricted = body.restrict_mode;
    setAllowAll(!restricted);
    setSavedAllowAll(!restricted);
    if (restricted && Array.isArray(body.allowed_providers)) {
      const set = new Set(body.allowed_providers);
      setEnabledServices(set);
      setSavedEnabledServices(new Set(set));
    } else if (!restricted) {
      setEnabledServices(new Set());
      setSavedEnabledServices(new Set());
    }
  }, []);

  const loadCatalog = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
        has_streams_only: streamsOnly ? 'true' : 'false',
      });
      if (debouncedQuery) params.set('query', debouncedQuery);
      if (category !== '__all__') params.set('category', category);
      const body = await openApiGET<CatalogResponse>(
        `/api/v1/settings/connectors/catalog?${params.toString()}`,
      );
      setStats(body.stats);
      setEnabledCount(body.enabled_provider_count);
      setCategories(body.categories);
      setRows(body.connectors);
      setTotalMatched(body.total_matched);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  }, [category, debouncedQuery, formatApiError, offset, streamsOnly]);

  const loadCategoryStats = useCallback(async () => {
    try {
      const body = await openApiGET<{
        category_breakdown: { category: string; total: number; enabled: number }[];
      }>('/api/v1/settings/connectors/catalog/stats');
      setCategoryBreakdown(body.category_breakdown ?? []);
    } catch (err) {
      toast.error(formatApiError(err));
    }
  }, [formatApiError]);

  useEffect(() => {
    void loadSummary().catch((err) => toast.error(formatApiError(err)));
    void loadCategoryStats();
  }, [formatApiError, loadCategoryStats, loadSummary]);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  function isRowEnabled(service: string): boolean {
    if (allowAll) return true;
    return enabledServices.has(service);
  }

  function toggleRow(service: string, checked: boolean) {
    void setServicePlatformEnabled(service, checked);
  }

  async function setServicePlatformEnabled(service: string, enabled: boolean) {
    if (enabled) {
      if (allowAll) return;
      setAllowAll(false);
      setEnabledServices((prev) => new Set(prev).add(service));
      return;
    }
    if (allowAll) {
      try {
        const body = await openApiGET<CatalogResponse>(
          '/api/v1/settings/connectors/catalog?limit=1500',
        );
        const next = new Set(body.connectors.map((c) => c.service));
        next.delete(service);
        setAllowAll(false);
        setEnabledServices(next);
      } catch (err) {
        toast.error(formatApiError(err));
      }
      return;
    }
    setAllowAll(false);
    setEnabledServices((prev) => {
      const next = new Set(prev);
      next.delete(service);
      return next;
    });
  }

  function exportAllowlist() {
    const doc = {
      schema: 'basis.platform.connector_allowlist/v1',
      exported_at: new Date().toISOString(),
      allowed_providers: allowlistFromDraft(allowAll, enabledServices),
      note: dirty ? ps.export_draft_note : undefined,
    };
    downloadTextBlob(
      'basis-platform-connector-allowlist.json',
      JSON.stringify(doc, null, 2),
      'application/json;charset=utf-8',
    );
    toast.success(ps.exported_toast);
  }

  async function applyImportedAllowlist(allowed: string[] | '*') {
    if (allowed === '*') {
      setAllowAll(true);
      setEnabledServices(new Set());
      toast.success(ps.import_applied_toast);
      return;
    }
    const validation = await openApiPOST<{ ok: boolean; unknown_providers: string[] }>(
      '/api/v1/settings/connectors/validate',
      { body: { allowed_providers: allowed } },
    );
    if (!validation.ok) {
      toast.error(
        fmt(ps.import_unknown_providers, {
          list: validation.unknown_providers.join(', '),
        }),
      );
      return;
    }
    setAllowAll(false);
    setEnabledServices(new Set(allowed));
    toast.success(ps.import_applied_toast);
  }

  function downloadImportTemplate() {
    const csv = rowsToCsv(['service', 'platform_enabled_draft'], [
      ['postgres', true],
      ['github', true],
      ['airtable', false],
    ]);
    downloadTextBlob('basis-platform-allowlist-template.csv', csv, 'text/csv;charset=utf-8');
  }

  function handleImportFile(file: File) {
    const reader = new FileReader();
    reader.onload = () => {
      void (async () => {
        try {
          const text = String(reader.result ?? '');
          const parsed = parsePlatformAllowlistFile(text, file.name);
          if (parsed === null) {
            toast.error(ps.import_invalid_error);
            return;
          }
          await applyImportedAllowlist(parsed);
        } catch {
          toast.error(ps.import_invalid_error);
        }
      })();
    };
    reader.readAsText(file);
  }

  async function exportCatalogCsv() {
    try {
      const body = await openApiGET<CatalogResponse>(
        '/api/v1/settings/connectors/catalog?limit=1500',
      );
      const csv = rowsToCsv(
        ['service', 'display_name', 'stream_count', 'tool_count', 'platform_enabled_draft'],
        body.connectors.map((row) => [
          row.service,
          row.display_name,
          row.stream_count,
          row.tool_count,
          isRowEnabled(row.service),
        ]),
      );
      downloadTextBlob('basis-platform-connectors-catalog.csv', csv, 'text/csv;charset=utf-8');
      if (body.stats.providers > body.connectors.length) {
        toast.message(ps.export_csv_truncated);
      } else {
        toast.success(ps.exported_csv_toast);
      }
    } catch (err) {
      toast.error(formatApiError(err));
    }
  }

  async function enableAllWithStreams() {
    try {
      const body = await openApiGET<CatalogResponse>(
        '/api/v1/settings/connectors/catalog?has_streams_only=true&limit=1500',
      );
      setAllowAll(false);
      setEnabledServices(new Set(body.connectors.map((c) => c.service)));
    } catch (err) {
      toast.error(formatApiError(err));
    }
  }

  function selectAllVisible() {
    setAllowAll(false);
    setEnabledServices((prev) => {
      const next = new Set(prev);
      for (const row of rows) next.add(row.service);
      return next;
    });
  }

  function clearAllVisible() {
    setAllowAll(false);
    setEnabledServices((prev) => {
      const next = new Set(prev);
      for (const row of rows) next.delete(row.service);
      return next;
    });
  }

  async function handleSave() {
    if (!allowAll && enabledServices.size === 0) {
      toast.error(ps.empty_selection_error);
      return;
    }
    setSaving(true);
    try {
      await openApiPUT('/api/v1/settings/connectors', {
        body: { allowed_providers: allowlistFromDraft(allowAll, enabledServices) },
      });
      toast.success(ps.saved_toast);
      await loadSummary();
      await loadCategoryStats();
      await loadCatalog();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  }

  const columns = useMemo<DataTableColumn<CatalogRow>[]>(
    () => [
      {
        key: 'enabled',
        header: ps.col_enabled,
        width: '2.5rem',
        render: (row) => (
          <div
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
            role="presentation"
          >
            <Checkbox
              checked={isRowEnabled(row.service)}
              disabled={allowAll}
              onCheckedChange={(checked) => toggleRow(row.service, checked === true)}
              aria-label={fmt(ps.toggle_provider_aria, { service: row.service })}
              data-testid={`platform-connector-enable-${row.service}`}
            />
          </div>
        ),
      },
      {
        key: 'service',
        header: ps.col_service,
        render: (row) => (
          <span className="font-mono text-xs font-medium text-foreground">{row.service}</span>
        ),
      },
      {
        key: 'name',
        header: ps.col_name,
        render: (row) => (
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">{row.display_name}</p>
            {row.description ? (
              <p className="line-clamp-1 text-xs text-muted-foreground">{row.description}</p>
            ) : null}
          </div>
        ),
      },
      {
        key: 'categories',
        header: ps.col_categories,
        hideBelow: 'md',
        render: (row) => (
          <div className="flex max-w-[14rem] flex-wrap gap-1">
            {(row.categories ?? []).slice(0, 3).map((cat) => (
              <Badge key={cat} variant="secondary" className="text-[10px] font-normal">
                {cat}
              </Badge>
            ))}
          </div>
        ),
      },
      {
        key: 'auth',
        header: ps.col_auth,
        hideBelow: 'lg',
        render: (row) => (
          <span className="font-mono text-[11px] text-muted-foreground">
            {(row.auth_modes ?? []).slice(0, 2).join(', ')}
          </span>
        ),
      },
      {
        key: 'streams',
        header: ps.col_streams,
        align: 'right',
        render: (row) => formatLocaleNumber(locale, row.stream_count),
      },
      {
        key: 'tools',
        header: ps.col_tools,
        align: 'right',
        hideBelow: 'md',
        render: (row) => formatLocaleNumber(locale, row.tool_count),
      },
      {
        key: 'manifest',
        header: '',
        width: '6rem',
        align: 'right',
        render: (row) => (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 text-xs"
            onClick={(e) => {
              e.stopPropagation();
              setDetailService(row.service);
              setDetailOpen(true);
            }}
            data-testid={`platform-connector-view-${row.service}`}
          >
            {ps.view_manifest}
          </Button>
        ),
      },
    ],
    [allowAll, enabledServices, locale, ps],
  );

  const selectedBreakdownCategory =
    category !== '__all__' ? category.toLowerCase() : undefined;

  function handleCategoryFromBreakdown(cat: string) {
    const match =
      categories.find((c) => c.toLowerCase() === cat.toLowerCase()) ?? cat;
    setCategory(match);
  }

  const pageEnd = offset + rows.length;
  const totalPages = Math.max(1, Math.ceil(totalMatched / PAGE_SIZE));
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
  const countLabel = `${fmt(ps.page_summary, {
    from: totalMatched === 0 ? 0 : offset + 1,
    to: pageEnd,
    total: totalMatched,
  })}${dirty ? ` · ${ps.unsaved_changes}` : ''}`;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      {stats ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: ps.stat_providers, value: stats.providers },
            { label: ps.stat_enabled, value: enabledCount },
            { label: ps.stat_with_streams, value: stats.providers_with_streams },
            { label: ps.stat_tools, value: stats.total_tools },
          ].map((item) => (
            <div key={item.label} className={cn(resourceCardSurfaceClass, 'px-4 py-3')}>
              <p className="text-xs text-muted-foreground">{item.label}</p>
              <p className="text-2xl font-semibold tabular-nums tracking-tight">
                {formatLocaleNumber(locale, item.value)}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <PlatformConnectorCategoryBreakdown
        rows={categoryBreakdown}
        selectedCategory={selectedBreakdownCategory}
        onSelectCategory={handleCategoryFromBreakdown}
      />

      <DataPanel>
        <DataPanelHeader
          title={ps.catalog_title}
          subtitle={ps.catalog_subtitle}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={allowAll}
                onClick={() => selectAllVisible()}
              >
                {ps.select_visible}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={allowAll}
                onClick={() => clearAllVisible()}
              >
                {ps.clear_visible}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() => void enableAllWithStreams()}
              >
                {ps.enable_stream_providers}
              </Button>
              <Button type="button" size="sm" variant="outline" onClick={() => exportAllowlist()}>
                {ps.export_allowlist}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => void exportCatalogCsv()}
              >
                {ps.export_catalog_csv}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => downloadImportTemplate()}
              >
                {ps.import_template}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => importInputRef.current?.click()}
              >
                {ps.import_allowlist}
              </Button>
              <input
                ref={importInputRef}
                type="file"
                accept="application/json,.json,text/csv,.csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleImportFile(file);
                  e.target.value = '';
                }}
              />
              <Button
                type="button"
                size="sm"
                disabled={!dirty || saving}
                onClick={() => void handleSave()}
                data-testid="save-platform-connector-allowlist-btn"
              >
                {saving ? ps.saving : ps.save_button}
              </Button>
            </div>
          }
        />
        <DataPanelBody padded={false}>
          <div className="space-y-3 border-b border-border px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Switch
                  id="platform-connector-allow-all"
                  checked={allowAll}
                  onCheckedChange={(checked) => {
                    setAllowAll(checked);
                    if (checked) setEnabledServices(new Set());
                  }}
                />
                <Label htmlFor="platform-connector-allow-all" className="text-sm">
                  {ps.allow_full_catalog}
                </Label>
              </div>
              <p className="text-xs text-muted-foreground">{ps.allow_full_catalog_hint}</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <ToolbarSearch
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={ps.search_placeholder}
                className="max-w-sm flex-1"
                data-testid="platform-connectors-catalog-search"
              />
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="w-[11rem]" size="sm">
                  <SelectValue placeholder={ps.category_all} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">{ps.category_all}</SelectItem>
                  {categories.map((cat) => (
                    <SelectItem key={cat} value={cat}>
                      {cat}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex items-center gap-2">
                <Switch
                  id="platform-streams-only"
                  checked={streamsOnly}
                  onCheckedChange={setStreamsOnly}
                />
                <Label htmlFor="platform-streams-only" className="text-xs whitespace-nowrap">
                  {ps.streams_only_filter}
                </Label>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              {ps.loading}
            </div>
          ) : (
            <DataTable
              columns={columns}
              data={rows}
              rowKey={(row) => row.service}
              className="border-0"
              onRowClick={(row) => {
                setDetailService(row.service);
                setDetailOpen(true);
              }}
            />
          )}

          <DataPanelTableFooter
            countLabel={countLabel}
            page={currentPage}
            totalPages={totalPages}
            onPageChange={(page) => setOffset((page - 1) * PAGE_SIZE)}
          />
        </DataPanelBody>
      </DataPanel>

      <PlatformConnectorManifestDialog
        service={detailService}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        allowAll={allowAll}
        platformEnabled={detailService ? isRowEnabled(detailService) : false}
        onPlatformEnabledChange={setServicePlatformEnabled}
      />
    </div>
  );
}
