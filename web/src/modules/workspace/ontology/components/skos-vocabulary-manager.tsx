import { Button } from "@/components/ui/button.js";
import { Input } from "@/components/ui/input.js";
import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleNumber, pickCountForm } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { useEffect, useState } from "react";
import { wsApiErrorMessage, wsGetJson } from '@/lib/workspace/ws-api-error';
import {
  ontologyApiSuffix,
  useOntologyWorkspaceId,
  vocabularyApiSuffix,
} from '@/components/app/shared/workspace/ontology-workspace-context.js';
import { cn } from "@/lib/utils.js";
import {
  ontErrorBanner,
  ontSkosBody,
  ontSkosBodyText,
  ontSkosCentered,
  ontSkosChip,
  ontSkosChipHidden,
  ontSkosChipRow,
  ontSkosDetailBody,
  ontSkosDetailHeader,
  ontSkosDetailPanel,
  ontSkosDetailTitle,
  ontSkosEmptyState,
  ontSkosErrorInset,
  ontSkosExpandBtn,
  ontSkosIconBtn,
  ontSkosLoadingRow,
  ontSkosNavLink,
  ontSkosNoteText,
  ontSkosPropSection,
  ontSkosPropSectionLabel,
  ontSkosSchemeHeaderBtn,
  ontSkosSchemePanel,
  ontSkosSchemeTitle,
  ontSkosSearchBar,
  ontSkosSearchInput,
  ontSkosShell,
  ontSkosToolbar,
  ontSkosTreeCol,
  ontSkosTreeCount,
  ontSkosTreeRow,
  ontSkosTreeRowSelected,
  ontSkosTreeSpacer,
  ontSkosUriLink,
  ontSkosUriMono,
} from "@/lib/ui-classes/ontology-ui.js";

interface SKOSScheme {
  uri: string;
  title: string;
  description?: string;
  concept_count: number;
}

interface ConceptNode {
  uri: string;
  pref_label: string;
  alt_labels?: string[];
  description?: string;
  notation?: string;
  scheme_uri?: string;
  parent_uri?: string;
  children?: ConceptNode[];
}

interface SKOSConceptDetail {
  uri: string;
  pref_label: string;
  alt_labels: string[];
  hidden_labels: string[];
  definition?: string;
  scope_note?: string;
  editorial_note?: string;
  broader: string[];
  narrower: string[];
  related: string[];
  exact_match: string[];
  close_match: string[];
  broad_match: string[];
  narrow_match: string[];
  scheme_uri?: string;
}

function countConcepts(nodes: ConceptNode[]): number {
  return nodes.reduce((acc, n) => acc + 1 + countConcepts(n.children ?? []), 0);
}

function LabelChip({ label }: { label: string }) {
  return <span className={ontSkosChip}>{label}</span>;
}

function UriLink({ uri }: { uri: string }) {
  const short = uri.includes("#") ? uri.split("#").pop() : uri.split("/").pop();
  return (
    <span title={uri} className={ontSkosUriLink}>
      {short || uri}
    </span>
  );
}

function ConceptDetailPanel({
  uri,
  onClose,
  onNavigate,
}: {
  uri: string;
  onClose: () => void;
  onNavigate: (uri: string) => void;
}) {
  const { t, locale } = useI18n();
  const s = t.ontology.hub.skos;
  const workspaceId = useOntologyWorkspaceId();
  const [detail, setDetail] = useState<SKOSConceptDetail | null>(null);
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
    void wsGetJson<SKOSConceptDetail>(
      workspaceId,
      ontologyApiSuffix(`skos/concept/${encodeURIComponent(uri)}`),
      {
        fallbackMessage: s.api.concept_not_found,
        partialWarning: s.api.partial_concept,
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
    return () => {
      ignore = true;
    };
  }, [workspaceId, uri, s.api, locale]);

  const renderUriList = (label: string, uris: string[]) => {
    if (!uris.length) return null;
    return (
      <PropSection label={label}>
        <div className="flex flex-col gap-1">
          {uris.map((u) => (
            <Button
              key={u}
              type="button"
              variant="ghost"
              className={cn(ontSkosNavLink, "h-auto w-full justify-start font-normal")}
              onClick={() => onNavigate(u)}
            >
              <PublicIcon name="chevron-right" className="size-2.5 shrink-0" />
              <UriLink uri={u} />
            </Button>
          ))}
        </div>
      </PropSection>
    );
  };

  return (
    <div className={ontSkosDetailPanel}>
      <div className={ontSkosDetailHeader}>
        <div className="flex min-w-0 items-center gap-2">
          <PublicIcon name="book-01" className="size-3.5 shrink-0 text-ok" />
          <span className="truncate text-sm font-bold text-foreground">{s.concept_detail}</span>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className={ontSkosIconBtn}
          onClick={onClose}
          aria-label={s.close_aria}
        >
          <PublicIcon name="x-02" className="size-3.5" />
        </Button>
      </div>

      {loading && (
        <div className={ontSkosCentered}>
          <PublicIcon name="loader-01" className="size-[18px] animate-spin text-primary" />
        </div>
      )}

      {error && (
        <div className={ontSkosCentered}>
          <PublicIcon name="alert-circle" className="size-4 text-destructive" />
          <span className="mt-1.5 text-xs text-destructive">{error}</span>
        </div>
      )}

      {detail && !loading && (
        <div className={ontSkosDetailBody}>
          <div className="mb-3.5">
            <h3 className={ontSkosDetailTitle}>{detail.pref_label}</h3>
            {detail.alt_labels.length > 0 && (
              <div className={ontSkosChipRow}>
                {detail.alt_labels.map((l) => <LabelChip key={l} label={l} />)}
              </div>
            )}
            {detail.hidden_labels.length > 0 && (
              <div className={ontSkosChipRow}>
                {detail.hidden_labels.map((l) => (
                  <span key={l} className={ontSkosChipHidden}>{l}</span>
                ))}
              </div>
            )}
            <div className={ontSkosUriMono}>{uri}</div>
          </div>

          {detail.definition && (
            <PropSection label={s.definition}>
              <p className={ontSkosBodyText}>{detail.definition}</p>
            </PropSection>
          )}

          {detail.scope_note && (
            <PropSection label={s.scope_note}>
              <p className={ontSkosNoteText}>{detail.scope_note}</p>
            </PropSection>
          )}

          {detail.editorial_note && (
            <PropSection label={s.editorial_note}>
              <p className={ontSkosNoteText}>{detail.editorial_note}</p>
            </PropSection>
          )}

          {renderUriList(s.broader, detail.broader)}
          {renderUriList(s.narrower, detail.narrower)}
          {renderUriList(s.related, detail.related)}
          {renderUriList(s.exact_match, detail.exact_match)}
          {renderUriList(s.close_match, detail.close_match)}
          {renderUriList(s.broad_match, detail.broad_match)}
          {renderUriList(s.narrow_match, detail.narrow_match)}

          {detail.scheme_uri && (
            <PropSection label={s.concept_scheme}>
              <span className="break-all font-mono text-[11px] text-muted-foreground">
                {detail.scheme_uri}
              </span>
            </PropSection>
          )}
        </div>
      )}
    </div>
  );
}

function PropSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={ontSkosPropSection}>
      <div className={ontSkosPropSectionLabel}>{label}</div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Concept tree node
// ---------------------------------------------------------------------------

function ConceptTreeNode({
  concept,
  depth,
  selectedUri,
  onSelect,
}: {
  concept: ConceptNode;
  depth: number;
  selectedUri: string | null;
  onSelect: (uri: string) => void;
}) {
  const { locale } = useI18n();
  const [expanded, setExpanded] = useState(depth === 0);
  const children = concept.children ?? [];
  const hasChildren = children.length > 0;
  const isSelected = selectedUri === concept.uri;

  return (
    <>
      <div
        className={cn(
          ontSkosTreeRow,
          isSelected && ontSkosTreeRowSelected,
          `pl-[${10 + depth * 14}px]`,
        )}
      >
        {hasChildren ? (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={(e) => {
              e.stopPropagation();
              setExpanded((v) => !v);
            }}
            className={ontSkosExpandBtn}
            aria-expanded={expanded}
          >
            {expanded ? <PublicIcon name="chevron-down" className="size-2.5" /> : <PublicIcon name="chevron-right" className="size-2.5" />}
          </Button>
        ) : (
          <span className={ontSkosTreeSpacer} aria-hidden />
        )}

        <span
          onClick={() => onSelect(concept.uri)}
          className={cn(
            "min-w-0 flex-1 truncate text-muted-foreground",
            depth === 0 ? "text-sm font-semibold" : "text-xs font-normal",
            isSelected && "text-foreground",
          )}
        >
          {concept.pref_label || concept.uri}
        </span>

        {hasChildren && (
          <span className={ontSkosTreeCount}>{formatLocaleNumber(locale, children.length)}</span>
        )}
      </div>

      {expanded &&
        hasChildren &&
        children.map((child) => (
          <ConceptTreeNode
            key={child.uri}
            concept={child}
            depth={depth + 1}
            selectedUri={selectedUri}
            onSelect={onSelect}
          />
        ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Scheme panel
// ---------------------------------------------------------------------------

function SchemePanel({
  scheme,
  selectedUri,
  onSelectConcept,
  searchQuery,
}: {
  scheme: SKOSScheme;
  selectedUri: string | null;
  onSelectConcept: (uri: string) => void;
  searchQuery: string;
}) {
  const { t, locale } = useI18n();
  const s = t.ontology.hub.skos;
  const workspaceId = useOntologyWorkspaceId();
  const [expanded, setExpanded] = useState(true);
  const [hierarchy, setHierarchy] = useState<ConceptNode[]>([]);
  const [loading, setLoading] = useState(expanded);
  const [error, setError] = useState("");

  const [prevExpanded, setPrevExpanded] = useState(expanded);
  const [prevSchemeUri, setPrevSchemeUri] = useState(scheme.uri);
  if (expanded !== prevExpanded || scheme.uri !== prevSchemeUri) {
    setPrevExpanded(expanded);
    setPrevSchemeUri(scheme.uri);
    if (expanded) {
      setLoading(true);
      setError("");
      setHierarchy([]);
    } else {
      setLoading(false);
    }
  }

  useEffect(() => {
    let ignore = false;
    if (!expanded) return;
    void wsGetJson<ConceptNode[]>(
      workspaceId,
      vocabularyApiSuffix("hierarchy"),
      {
        query: { scheme: scheme.uri },
        fallbackMessage: s.api.hierarchy_failed,
        partialWarning: s.api.partial_hierarchy,
        locale: locale as Locale,
      },
    )
      .then(({ data, partialWarning }) => {
        if (ignore) return;
        if (partialWarning) setError(partialWarning);
        setHierarchy(data);
      })
      .catch((err) => {
        if (!ignore) {
          setHierarchy([]);
          setError(wsApiErrorMessage(err, locale as Locale));
        }
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });
    return () => {
      ignore = true;
    };
  }, [workspaceId, scheme.uri, expanded, s.api, locale]);

  const totalConcepts = countConcepts(hierarchy);
  const conceptCountLabel = loading
    ? t.core.common.ellipsis
    : fmt(pickCountForm(locale, totalConcepts, s.concept_count_one, s.concept_count), {
        count: formatLocaleNumber(locale, totalConcepts),
      });

  const filterConcepts = (nodes: ConceptNode[], q: string): ConceptNode[] => {
    if (!q) return nodes;
    return nodes.flatMap((n) => {
      const match = (n.pref_label + " " + (n.alt_labels?.join(" ") ?? "") + " " + (n.description ?? ""))
        .toLowerCase()
        .includes(q.toLowerCase());
      const filteredChildren = filterConcepts(n.children ?? [], q);
      if (match || filteredChildren.length > 0) {
        return [{ ...n, children: filteredChildren }];
      }
      return [];
    });
  };

  const displayedConcepts = filterConcepts(hierarchy, searchQuery);

  return (
    <div className={ontSkosSchemePanel}>
      <Button
        type="button"
        variant="ghost"
        className={cn(ontSkosSchemeHeaderBtn, "h-auto w-full font-normal")}
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <PublicIcon name="chevron-down" className="size-3.5 text-muted-foreground" />
          ) : (
            <PublicIcon name="chevron-right" className="size-3.5 text-muted-foreground" />
          )}
          <span className={ontSkosSchemeTitle}>{scheme.title}</span>
        </div>
        <span className="text-[11px] text-muted-foreground">{conceptCountLabel}</span>
      </Button>

      {expanded && (
        <div className="pb-2">
          {error ? <div className={cn(ontErrorBanner, "m-2")}>{error}</div> : null}
          {loading ? (
            <div className={ontSkosLoadingRow}>
              <PublicIcon name="loader-01" className="size-3 animate-spin text-primary" />
              <span className="text-xs text-muted-foreground">{s.loading_concepts}</span>
            </div>
          ) : displayedConcepts.length === 0 ? (
            <div className="px-6 py-2 text-xs italic text-muted-foreground">
              {searchQuery ? s.no_matching_concepts : s.no_concepts_in_scheme}
            </div>
          ) : (
            <div className="pt-0.5">
              {displayedConcepts.map((concept) => (
                <ConceptTreeNode
                  key={concept.uri}
                  concept={concept}
                  depth={0}
                  selectedUri={selectedUri}
                  onSelect={onSelectConcept}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main SKOSVocabularyManager
// ---------------------------------------------------------------------------

interface Props {
  schemeUri?: string;
}

export function SKOSVocabularyManager({ schemeUri }: Props) {
  const { t, locale } = useI18n();
  const s = t.ontology.hub.skos;
  const workspaceId = useOntologyWorkspaceId();
  const [schemes, setSchemes] = useState<SKOSScheme[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [selectedUri, setSelectedUri] = useState<string | null>(null);

  useEffect(() => {
    void wsGetJson<SKOSScheme[]>(
      workspaceId,
      ontologyApiSuffix("skos/schemes"),
      {
        fallbackMessage: s.api.schemes_failed,
        partialWarning: s.api.partial_schemes,
        locale: locale as Locale,
      },
    )
      .then(({ data, partialWarning }) => {
        if (partialWarning) setError(partialWarning);
        setSchemes(data);
      })
      .catch((e) => setError(wsApiErrorMessage(e, locale as Locale)))
      .finally(() => setLoading(false));
  }, [workspaceId, s.api, locale]);

  const displayedSchemes = schemeUri
    ? schemes.filter((s) => s.uri === schemeUri)
    : schemes;

  return (
    <div className={ontSkosShell}>
      {error ? <div className={cn(ontErrorBanner, ontSkosErrorInset)}>{error}</div> : null}
      <div className={ontSkosToolbar}>
        <div className={ontSkosSearchBar}>
          <PublicIcon name="search-01" className="size-3.5 shrink-0 text-muted-foreground" />
          <Input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder={s.search_placeholder}
            className={cn(ontSkosSearchInput, "h-8 border-0 bg-transparent shadow-none focus-visible:ring-0")}
          />
          {searchQ ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              className={ontSkosIconBtn}
              onClick={() => setSearchQ("")}
              aria-label={s.clear_aria}
            >
              <PublicIcon name="x-02" className="size-2.5" />
            </Button>
          ) : null}
        </div>
      </div>

      <div className={ontSkosBody}>
        <div className={ontSkosTreeCol}>
          {loading && (
            <div className={ontSkosCentered}>
              <PublicIcon name="loader-01" className="size-[18px] animate-spin text-primary" />
            </div>
          )}

          {error && (
            <div className={ontSkosCentered}>
              <PublicIcon name="alert-circle" className="size-4 text-destructive" />
              <span className="mt-1.5 text-xs text-destructive">{error}</span>
            </div>
          )}

          {!loading && !error && displayedSchemes.length === 0 && (
            <div className={ontSkosEmptyState}>
              <PublicIcon name="book-01" className="size-7 text-primary/15" />
              <span className="mt-2.5 text-xs text-muted-foreground">{s.empty_schemes}</span>
              <span className="mt-1 max-w-[220px] text-[11px] text-muted-foreground">
                {s.empty_schemes_hint}
              </span>
            </div>
          )}

          {!loading &&
            displayedSchemes.map((scheme) => (
              <SchemePanel
                key={scheme.uri}
                scheme={scheme}
                selectedUri={selectedUri}
                onSelectConcept={setSelectedUri}
                searchQuery={searchQ}
              />
            ))}
        </div>

        {selectedUri ? (
          <ConceptDetailPanel
            uri={selectedUri}
            onClose={() => setSelectedUri(null)}
            onNavigate={setSelectedUri}
          />
        ) : null}
      </div>
    </div>
  );
}
