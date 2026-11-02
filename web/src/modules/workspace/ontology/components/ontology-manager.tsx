import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useCallback, useEffect, useState } from "react";
import {
  wsApiErrorMessage,
  wsGetJson,
  wsMutationResult,
  parseWsJson,
  throwIfWsNotOk,
} from '@/lib/workspace/ws-api-error';
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import {
  ontologyApiSuffix,
  useOntologyWorkspaceId,
} from '@/components/app/shared/workspace/ontology-workspace-context.js';
import { OntologyLoader } from "./ontology-loader";
import { OntologySearch } from "./ontology-search";
import { SKOSVocabularyManager } from "./skos-vocabulary-manager";
import { Button } from "@/components/ui/button.js";
import { Input } from "@/components/ui/input.js";
import { useI18n } from "@/i18n/context.js";
import type { Locale } from "@/i18n/locale.js";
import { fmt, formatLocaleDateTime, formatLocaleNumber, pickCountForm } from "@/i18n/format.js";
import { cn } from "@/lib/utils.js";
import {
  ontManagerActionBtn,
  ontManagerBrowseBtn,
  ontManagerCentered,
  ontManagerCloseBtn,
  ontManagerDetailBody,
  ontManagerDisabledBadge,
  ontManagerList,
  ontManagerListHeader,
  ontManagerListPanel,
  ontManagerMain,
  ontManagerRightHeader,
  ontManagerRightPanel,
  ontManagerRow,
  ontManagerRowActions,
  ontManagerRowMain,
  ontManagerRowName,
  ontManagerRowStats,
  ontManagerRowUri,
  ontManagerSearchBox,
  ontManagerSearchInput,
  ontManagerShell,
  ontManagerSourceLink,
  ontManagerStatRow,
  ontManagerTagChip,
  ontManagerToolbar,
  ontStatLabel,
  ontStatValue,
} from "@/lib/ui-classes/ontology-ui.js";

interface OntologyEntry {
  uri: string;
  name: string;
  description?: string;
  format: string;
  status: "published" | "draft" | "external";
  source_url?: string;
  version?: string;
  class_count: number;
  concept_count: number;
  property_count: number;
  loaded_at: string;
  enabled: boolean;
  tags: string[];
}

type RightPanel = "none" | "search" | "skos";

const STATUS_CLASS: Record<string, string> = {
  published: "border-ok/30 bg-ok/10 text-ok",
  draft: "border-warn/30 bg-warn/10 text-warn",
  external: "border-primary/30 bg-primary/10 text-primary",
};

const FORMAT_CLASS: Record<string, string> = {
  turtle: "border-ok/25 bg-ok/10 text-ok",
  xml: "border-destructive/25 bg-destructive/10 text-destructive",
  "json-ld": "border-warn/25 bg-warn/10 text-warn",
  nt: "border-primary/25 bg-primary/10 text-primary",
};

const badgeBase =
  "rounded-full border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide";

function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const labels = t.ontology.hub.manager.status_labels;
  const label = labels[status as keyof typeof labels] ?? status;
  return (
    <span className={cn(badgeBase, STATUS_CLASS[status] ?? "border-border bg-muted text-muted-foreground")}>
      {label}
    </span>
  );
}

function FormatBadge({ format }: { format: string }) {
  const { t } = useI18n();
  const key = format.toLowerCase();
  const labels = t.ontology.hub.manager.format_labels;
  const label = labels[key as keyof typeof labels] ?? format;
  return (
    <span className={cn(badgeBase, FORMAT_CLASS[format] ?? "border-border bg-muted text-muted-foreground")}>
      {label}
    </span>
  );
}

function Stat({ locale, value, label }: { locale: Locale; value: number; label: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className={ontStatValue}>{formatLocaleNumber(locale, value)}</span>
      <span className={ontStatLabel}>{label}</span>
    </div>
  );
}

function RegistryRow({
  entry,
  selected,
  onSelect,
  onToggle,
  onRefresh,
  onRemove,
}: {
  entry: OntologyEntry;
  selected: boolean;
  onSelect: (e: OntologyEntry) => void;
  onToggle: (uri: string) => void;
  onRefresh: (uri: string) => void;
  onRemove: (uri: string) => void;
}) {
  const { t, locale } = useI18n();
  const m = t.ontology.hub.manager;
  const [busyToggle, setBusyToggle] = useState(false);
  const [busyRefresh, setBusyRefresh] = useState(false);
  const [busyRemove, setBusyRemove] = useState(false);

  const handleToggle = async (ev: React.MouseEvent) => {
    ev.stopPropagation();
    setBusyToggle(true);
    await onToggle(entry.uri);
    setBusyToggle(false);
  };

  const handleRefresh = async (ev: React.MouseEvent) => {
    ev.stopPropagation();
    setBusyRefresh(true);
    await onRefresh(entry.uri);
    setBusyRefresh(false);
  };

  const handleRemove = async (ev: React.MouseEvent) => {
    ev.stopPropagation();
    if (!window.confirm(fmt(m.remove_confirm, { name: entry.name }))) return;
    setBusyRemove(true);
    await onRemove(entry.uri);
    setBusyRemove(false);
  };

  return (
    <div
      onClick={() => onSelect(entry)}
      className={cn(
        ontManagerRow,
        selected ? "border-primary/30 bg-primary/10" : "border-border bg-card/50 hover:bg-muted/40",
        !entry.enabled && "opacity-55",
      )}
    >
      <div className={ontManagerRowMain}>
        <div className="flex flex-wrap items-center gap-2">
          <span className={ontManagerRowName}>{entry.name}</span>
          <StatusBadge status={entry.status} />
          <FormatBadge format={entry.format} />
          {!entry.enabled && (
            <span className={ontManagerDisabledBadge}>{m.disabled}</span>
          )}
        </div>
        <div className={ontManagerRowUri}>{entry.uri}</div>
        {entry.source_url && (
          <a
            href={entry.source_url}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className={ontManagerSourceLink}
          >
            <PublicIcon name="link-external" size={10} />
            {entry.source_url.slice(0, 60)}
            {entry.source_url.length > 60 ? t.core.common.ellipsis : ""}
          </a>
        )}
      </div>

      <div className={ontManagerRowStats}>
        <Stat locale={locale} value={entry.class_count} label={m.stat_classes} />
        <Stat locale={locale} value={entry.concept_count} label={m.stat_concepts} />
        <Stat locale={locale} value={entry.property_count} label={m.stat_props} />
      </div>

      <div className={ontManagerRowActions}>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          title={entry.enabled ? m.disable : m.enable}
          onClick={handleToggle}
          disabled={busyToggle}
          className={ontManagerActionBtn}
        >
          {busyToggle ? (
            <PublicIcon name="loader-01" size={13} className="animate-spin" />
          ) : entry.enabled ? (
            <PublicIcon name="toggle-right" size={15} className="text-ok" />
          ) : (
            <PublicIcon name="toggle-left" size={15} className="text-muted-foreground" />
          )}
        </Button>

        {entry.source_url && (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            title={m.refresh_title}
            onClick={handleRefresh}
            disabled={busyRefresh}
            className={ontManagerActionBtn}
          >
            {busyRefresh ? (
              <PublicIcon name="loader-01" size={13} className="animate-spin" />
            ) : (
              <PublicIcon name="arrow-refresh-01" size={13} className="text-primary" />
            )}
          </Button>
        )}

        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          title={m.remove_title}
          onClick={handleRemove}
          disabled={busyRemove}
          className={cn(ontManagerActionBtn, "text-destructive hover:text-destructive")}
        >
          {busyRemove ? (
            <PublicIcon name="loader-01" size={13} className="animate-spin" />
          ) : (
            <PublicIcon name="trash-01" size={13} />
          )}
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function OntologyManager({
  pageActionsHosted = false,
  onHubPageActionsChange,
}: {
  pageActionsHosted?: boolean;
  onHubPageActionsChange?: (actions: { openLoadOntology: () => void } | null) => void;
} = {}) {
  const { t, locale } = useI18n();
  const m = t.ontology.hub.manager;
  const workspaceId = useOntologyWorkspaceId();
  const [entries, setEntries] = useState<OntologyEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQ, setSearchQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showLoader, setShowLoader] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<OntologyEntry | null>(null);
  const [rightPanel, setRightPanel] = useState<RightPanel>("none");
  const [actionMsg, setActionMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const [prevSearchQ, setPrevSearchQ] = useState(searchQ);
  if (searchQ !== prevSearchQ) {
    setPrevSearchQ(searchQ);
    setLoading(true);
    setActionMsg(null);
  }

  const flashMsg = useCallback((type: "ok" | "err", text: string) => {
    setActionMsg({ type, text });
    setTimeout(() => setActionMsg(null), 3000);
  }, []);

  useEffect(() => {
    if (!pageActionsHosted || !onHubPageActionsChange) return;
    onHubPageActionsChange({ openLoadOntology: () => setShowLoader(true) });
    return () => onHubPageActionsChange(null);
  }, [onHubPageActionsChange, pageActionsHosted]);

  const fetchRegistry = useCallback(async () => {
    setLoading(true);
    setActionMsg(null);
    try {
      const { data, partialWarning } = await wsGetJson<OntologyEntry[]>(
        workspaceId,
        ontologyApiSuffix("registry"),
        {
          query: searchQ ? { q: searchQ } : undefined,
          fallbackMessage: m.api.load_registry_failed,
          partialWarning: m.api.partial_registry,
          locale: locale as Locale,
        },
      );
      setEntries(data);
      if (partialWarning) flashMsg("err", partialWarning);
    } catch (err) {
      setEntries([]);
      flashMsg("err", wsApiErrorMessage(err, locale as Locale));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, searchQ, flashMsg, locale, m.api]);

  useEffect(() => {
    let ignore = false;
    async function fetchInitial() {
      try {
        const { data, partialWarning } = await wsGetJson<OntologyEntry[]>(
          workspaceId,
          ontologyApiSuffix("registry"),
          {
            query: searchQ ? { q: searchQ } : undefined,
            fallbackMessage: m.api.load_registry_failed,
            partialWarning: m.api.partial_registry,
            locale: locale as Locale,
          },
        );
        if (ignore) return;
        setEntries(data);
        if (partialWarning) flashMsg("err", partialWarning);
      } catch (err) {
        if (!ignore) {
          setEntries([]);
          flashMsg("err", wsApiErrorMessage(err, locale as Locale));
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    void fetchInitial();
    return () => { ignore = true; };
  }, [workspaceId, searchQ, flashMsg, locale, m.api]);

  const handleToggle = useCallback(async (uri: string) => {
    try {
      const res = await workspaceOpenApiResponse(
        'PATCH',
        workspaceId,
        ontologyApiSuffix(`${encodeURIComponent(uri)}/toggle`),
      );
      const data = await parseWsJson<{ enabled: boolean }>(res, m.api.toggle_failed);
      setEntries((prev) =>
        prev.map((e) => (e.uri === uri ? { ...e, enabled: data.enabled } : e))
      );
    } catch (err) {
      flashMsg("err", wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, locale, m.api]);

  const handleRefresh = useCallback(async (uri: string) => {
    try {
      const res = await workspaceOpenApiResponse(
        'POST',
        workspaceId,
        ontologyApiSuffix(`${encodeURIComponent(uri)}/refresh`),
      );
      const partial = await wsMutationResult(
        res,
        m.api.refresh_failed,
        m.api.partial_refresh,
        locale as Locale,
      );
      if (partial) flashMsg("err", partial);
      else flashMsg("ok", m.api.refreshed_ok);
      fetchRegistry();
    } catch (err) {
      flashMsg("err", wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, fetchRegistry, locale, m.api]);

  const handleRemove = useCallback(async (uri: string) => {
    try {
      const res = await workspaceOpenApiResponse(
        'DELETE',
        workspaceId,
        ontologyApiSuffix(encodeURIComponent(uri)),
      );
      await throwIfWsNotOk(res, m.api.remove_failed);
      setEntries((prev) => prev.filter((e) => e.uri !== uri));
      if (selectedEntry?.uri === uri) setSelectedEntry(null);
      flashMsg("ok", m.api.removed_ok);
    } catch (err) {
      flashMsg("err", wsApiErrorMessage(err, locale as Locale));
    }
  }, [workspaceId, locale, m.api, selectedEntry]);

  const handleSelect = (entry: OntologyEntry) => {
    setSelectedEntry((prev) => (prev?.uri === entry.uri ? null : entry));
    setRightPanel("none");
  };

  const handleLoaded = () => {
    setShowLoader(false);
    fetchRegistry();
  };

  const filteredEntries = entries.filter((e) => {
    if (statusFilter === "owl") return ["owl:Ontology"].includes(e.format) || e.format === "xml" || e.format === "turtle";
    if (statusFilter === "skos") return e.concept_count > 0;
    if (statusFilter === "internal") return e.status === "draft" || e.status === "published";
    if (statusFilter === "external") return e.status === "external";
    return true;
  });

  const isSKOS = selectedEntry ? selectedEntry.concept_count > 0 : false;

  return (
    <>
      {showLoader && (
        <OntologyLoader
          onLoaded={handleLoaded}
          onClose={() => setShowLoader(false)}
        />
      )}

      <div className={ontManagerShell}>
        <div className={ontManagerToolbar}>
          <div className={ontManagerSearchBox}>
            <PublicIcon name="search-01" size={14} className="text-muted-foreground" />
            <Input
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder={m.search_placeholder}
              className={cn(ontManagerSearchInput, "h-8 border-0 bg-transparent shadow-none focus-visible:ring-0")}
            />
          </div>

          <div className="flex flex-wrap gap-1.5">
            {(["all", "owl", "skos", "internal", "external"] as const).map((f) => (
              <Button
                key={f}
                type="button"
                size="sm"
                variant={statusFilter === f ? "secondary" : "ghost"}
                className="h-7 px-2.5 text-[11px] font-semibold uppercase"
                onClick={() => setStatusFilter(f)}
              >
                {m.filters[f]}
              </Button>
            ))}
          </div>

          <div className="ml-auto flex gap-2">
            <Button
              type="button"
              size="sm"
              variant={rightPanel === "search" ? "secondary" : "outline"}
              onClick={() => setRightPanel((p) => (p === "search" ? "none" : "search"))}
            >
              <PublicIcon name="search-01" size={13} />
              {m.entity_search}
            </Button>
            {!pageActionsHosted ? (
              <Button type="button" size="sm" onClick={() => setShowLoader(true)}>
                <PublicIcon name="plus-01" size={13} />
                {m.load_ontology}
              </Button>
            ) : null}
          </div>
        </div>

        {actionMsg && (
          <div
            className={cn(
              "flex shrink-0 items-center gap-2 border-b px-4 py-2 text-xs",
              actionMsg.type === "ok"
                ? "border-ok/25 bg-ok/10 text-ok"
                : "border-destructive/25 bg-destructive/10 text-destructive",
            )}
          >
            {actionMsg.type === "ok" ? (
              <PublicIcon name="check-circle" size={13} />
            ) : (
              <PublicIcon name="alert-circle" size={13} />
            )}
            {actionMsg.text}
          </div>
        )}

        {/* Main content area */}
        <div className={ontManagerMain}>
          <div className={ontManagerListPanel}>
            {loading ? (
              <div className={ontManagerCentered}>
                <PublicIcon name="loader-01" size={22} className="animate-spin text-primary" />
                <span className="mt-2.5 text-sm text-muted-foreground">{m.loading_registry}</span>
              </div>
            ) : filteredEntries.length === 0 ? (
              <div className={cn(ontManagerCentered, "text-center")}>
                <PublicIcon name="bookmark" size={36} className="text-primary/20" />
                <div className="mt-3.5 text-sm font-semibold text-muted-foreground">
                  {searchQ ? m.empty_search_title : m.empty_title}
                </div>
                <div className="mt-1.5 max-w-[300px] text-center text-xs leading-relaxed text-muted-foreground">
                  {searchQ ? m.empty_search_body : m.empty_body}
                </div>
                {!searchQ && !pageActionsHosted ? (
                  <Button type="button" size="sm" className="mt-4" onClick={() => setShowLoader(true)}>
                    <PublicIcon name="plus-01" size={13} />
                    {m.load_ontology}
                  </Button>
                ) : null}
              </div>
            ) : (
              <div className={ontManagerList}>
                <div className={ontManagerListHeader}>
                  <span>
                    {fmt(
                      pickCountForm(locale, filteredEntries.length, m.registry_count_one, m.registry_count),
                      { count: formatLocaleNumber(locale, filteredEntries.length) },
                    )}
                  </span>
                </div>
                {filteredEntries.map((entry) => (
                  <RegistryRow
                    key={entry.uri}
                    entry={entry}
                    selected={selectedEntry?.uri === entry.uri}
                    onSelect={handleSelect}
                    onToggle={handleToggle}
                    onRefresh={handleRefresh}
                    onRemove={handleRemove}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Right panel */}
          {rightPanel === "search" && (
            <div className={ontManagerRightPanel}>
              <div className={ontManagerRightHeader}>
                <span className="truncate text-sm font-bold text-foreground">{m.entity_search}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className={ontManagerCloseBtn}
                  onClick={() => setRightPanel("none")}
                >
                  ×
                </Button>
              </div>
              <OntologySearch />
            </div>
          )}

          {rightPanel === "none" && selectedEntry && (
            <div className={ontManagerRightPanel}>
              <div className={ontManagerRightHeader}>
                <span className="truncate text-sm font-bold text-foreground">{selectedEntry.name}</span>
                <div className="flex gap-1.5">
                  {isSKOS && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className={ontManagerBrowseBtn}
                      onClick={() => setRightPanel("skos")}
                    >
                      <PublicIcon name="book-01" size={12} />
                      {m.browse_skos}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={ontManagerCloseBtn}
                    onClick={() => setSelectedEntry(null)}
                  >
                    ×
                  </Button>
                </div>
              </div>
              <div className={ontManagerDetailBody}>
                <DetailSection label={m.detail_uri}>
                  <span className="break-all font-mono text-[11px] text-muted-foreground">
                    {selectedEntry.uri}
                  </span>
                </DetailSection>
                {selectedEntry.description && (
                  <DetailSection label={m.detail_description}>
                    <span className="text-sm leading-relaxed text-muted-foreground">
                      {selectedEntry.description}
                    </span>
                  </DetailSection>
                )}
                {selectedEntry.source_url && (
                  <DetailSection label={m.detail_source_url}>
                    <a
                      href={selectedEntry.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="break-all text-[11px] text-primary hover:underline"
                    >
                      {selectedEntry.source_url}
                    </a>
                  </DetailSection>
                )}
                {selectedEntry.version && (
                  <DetailSection label={m.detail_version}>
                    <span className="text-xs text-muted-foreground">{selectedEntry.version}</span>
                  </DetailSection>
                )}
                {selectedEntry.loaded_at && (
                  <DetailSection label={m.detail_loaded_at}>
                    <span className="text-xs text-muted-foreground">
                      {formatLocaleDateTime(locale, selectedEntry.loaded_at)}
                    </span>
                  </DetailSection>
                )}
                <div className={ontManagerStatRow}>
                  <StatBlock locale={locale} value={selectedEntry.class_count} label={m.stat_classes} tone="primary" />
                  <StatBlock locale={locale} value={selectedEntry.concept_count} label={m.stat_concepts} tone="ok" />
                  <StatBlock locale={locale} value={selectedEntry.property_count} label={m.stat_props} tone="warn" />
                </div>
                {selectedEntry.tags.length > 0 && (
                  <DetailSection label={m.detail_tags}>
                    <div className="flex flex-wrap gap-1.5">
                      {selectedEntry.tags.map((tag) => (
                        <span key={tag} className={ontManagerTagChip}>{tag}</span>
                      ))}
                    </div>
                  </DetailSection>
                )}
              </div>
            </div>
          )}

          {rightPanel === "skos" && selectedEntry && (
            <div className={ontManagerRightPanel}>
              <div className={ontManagerRightHeader}>
                <span className="truncate text-sm font-bold text-foreground">
                  {fmt(m.skos_panel_title, { name: selectedEntry.name })}
                </span>
                <div className="flex gap-1.5">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className={ontManagerBrowseBtn}
                    onClick={() => setRightPanel("none")}
                  >
                    <PublicIcon name="stack" size={12} />
                    {m.registry_detail}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className={ontManagerCloseBtn}
                    onClick={() => setRightPanel("none")}
                  >
                    ×
                  </Button>
                </div>
              </div>
              <SKOSVocabularyManager schemeUri={selectedEntry.uri} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}

/* ─── sub-components ─────────────────────────────────────────────────── */

function DetailSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border/60 pb-0.5 pt-2.5">
      <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      {children}
    </div>
  );
}

function StatBlock({
  locale,
  value,
  label,
  tone,
}: {
  locale: Locale;
  value: number;
  label: string;
  tone: "primary" | "ok" | "warn";
}) {
  const toneClass =
    tone === "ok" ? "text-ok" : tone === "warn" ? "text-warn" : "text-primary";
  return (
    <div className="flex flex-1 flex-col items-center gap-0.5 rounded-lg border border-border bg-muted/30 px-1.5 py-2.5">
      <span className={cn("text-lg font-extrabold", toneClass)}>{formatLocaleNumber(locale, value)}</span>
      <span className="text-[10px] text-muted-foreground">{label}</span>
    </div>
  );
}
