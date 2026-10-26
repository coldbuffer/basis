import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { cn } from "@/lib/utils.js";
import {
  ontAlignMatrixCell,
  ontAlignMatrixCellDiag,
  ontAlignMatrixColHeader,
  ontAlignMatrixCorner,
  ontAlignMatrixRowHeader,
  ontAlignMatrixTable,
  ontAlignMatrixWrap,
  ontAlignRelationBadge,
  ontAlignRelationClass,
  ontAlignSuggestList,
  ontStrong,
} from "@/lib/ui-classes/ontology-ui.js";
import { govOhMuted, govOhSuggestion } from "@/lib/ui-classes/governance-ui.js";
import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useI18n } from "@/i18n/context.js";
import { formatLocaleFixedDecimals } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { Button } from "@/components/ui/button.js";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.js";
import { Input } from "@/components/ui/input.js";
import { Label } from "@/components/ui/label.js";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select.js";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select.js";
import { Slider } from "@/components/ui/slider.js";
import { Textarea } from "@/components/ui/textarea.js";
import {
  loadAlignments,
  loadOntologyRegistry,
  removeAlignment,
  saveAlignment,
  suggestAlignments,
} from '../lib/api.js';
import { useOntologyWorkspaceId } from "./ontology-workspace-context";
import { workspaceReviewPath } from '@/lib/nav/nav-config.js';
import { wsApiErrorMessage } from '@/lib/workspace/ws-api-error';
import type { LocaleMessages } from "@/i18n/en.js";
import type { AlignmentRelation, AlignmentSuggestion, OntologyAlignment, OntologyEntry } from '../lib/types.js';

const RELATIONS: AlignmentRelation[] = [
  "owl:equivalentClass",
  "owl:equivalentProperty",
  "skos:exactMatch",
  "skos:closeMatch",
  "skos:broadMatch",
  "skos:narrowMatch",
  "skos:relatedMatch",
];

function relationBadgeClass(relation: AlignmentRelation) {
  return ontAlignRelationClass[relation] ?? "border-border text-muted-foreground";
}

function alignmentRelationLabel(
  copy: LocaleMessages['ontology']['alignments'],
  relation: AlignmentRelation,
): string {
  const labels = copy.relation_labels as Record<string, string>;
  return labels[relation] ?? relation;
}

export function AlignmentsPanel() {
  const workspaceId = useOntologyWorkspaceId();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t, locale } = useI18n();
  const copy = t.ontology.alignments;
  const apiLocale = locale as Locale;
  const [registry, setRegistry] = useState<OntologyEntry[]>([]);
  const [alignments, setAlignments] = useState<OntologyAlignment[]>([]);
  const [suggestions, setSuggestions] = useState<AlignmentSuggestion[]>([]);
  const [sourceOntology, setSourceOntology] = useState("");
  const [targetOntology, setTargetOntology] = useState("");
  const [sourceUri, setSourceUri] = useState("");
  const [targetUri, setTargetUri] = useState("");
  const [relation, setRelation] = useState<AlignmentRelation>("skos:exactMatch");
  const [confidence, setConfidence] = useState(0.86);
  const [provenance, setProvenance] = useState("");
  const [source, setSource] = useState<string>(copy.default_source);
  const prevDefaultSourceRef = useRef(copy.default_source);
  useEffect(() => {
    const prevDefault = prevDefaultSourceRef.current;
    prevDefaultSourceRef.current = copy.default_source;
    setSource((current) =>
      current === prevDefault || current === "" ? copy.default_source : current,
    );
  }, [copy.default_source]);
  const [reviewer, setReviewer] = useState("");
  const [threshold, setThreshold] = useState(0.68);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [suggestOpen, setSuggestOpen] = useState(false);

  useEffect(() => {
    const ontologyUri = searchParams.get('alignOntology')?.trim();
    if (ontologyUri) {
      setSourceOntology(ontologyUri);
    }
    if (searchParams.get('alignSuggest') !== '1') {
      if (ontologyUri) {
        const next = new URLSearchParams(searchParams);
        next.delete('alignOntology');
        setSearchParams(next, { replace: true });
      }
      return;
    }
    setSuggestOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete('alignSuggest');
    next.delete('alignOntology');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const reload = useCallback(async () => {
    setError("");
    const [registryResult, alignmentResult] = await Promise.allSettled([
      loadOntologyRegistry(workspaceId, { locale: apiLocale }),
      loadAlignments(workspaceId, undefined, { locale: apiLocale }),
    ]);

    const errors: string[] = [];
    if (registryResult.status === "fulfilled") {
      setRegistry(registryResult.value);
      setSourceOntology((current) => current || registryResult.value[0]?.uri || "");
      setTargetOntology((current) => current || registryResult.value[1]?.uri || registryResult.value[0]?.uri || "");
    } else {
      errors.push(wsApiErrorMessage(registryResult.reason, apiLocale));
    }
    if (alignmentResult.status === "fulfilled") {
      setAlignments(alignmentResult.value);
    } else {
      errors.push(wsApiErrorMessage(alignmentResult.reason, apiLocale));
    }
    if (errors.length) setError(errors.join(" "));
  }, [apiLocale, workspaceId]);

  useEffect(() => {
    let ignore = false;
    async function fetchInitial() {
      const [registryResult, alignmentResult] = await Promise.allSettled([
        loadOntologyRegistry(workspaceId, { locale: apiLocale }),
        loadAlignments(workspaceId, undefined, { locale: apiLocale }),
      ]);
      if (ignore) return;

      const errors: string[] = [];
      if (registryResult.status === "fulfilled") {
        setRegistry(registryResult.value);
        setSourceOntology((current) => current || registryResult.value[0]?.uri || "");
        setTargetOntology((current) => current || registryResult.value[1]?.uri || registryResult.value[0]?.uri || "");
      } else {
        errors.push(wsApiErrorMessage(registryResult.reason, apiLocale));
      }
      if (alignmentResult.status === "fulfilled") {
        setAlignments(alignmentResult.value);
      } else {
        errors.push(wsApiErrorMessage(alignmentResult.reason, apiLocale));
      }
      if (errors.length) setError(errors.join(" "));
    }
    void fetchInitial();
    return () => { ignore = true; };
  }, [apiLocale, workspaceId]);

  // Pairwise matrix: group alignments by (source_ontology, target_ontology) pair.
  const matrix = useMemo(() => {
    function ontologyOfUri(uri: string): string {
      for (const entry of registry) {
        if (uri === entry.uri || uri.startsWith(entry.uri + "#") || uri.startsWith(entry.uri + "/")) {
          return entry.uri;
        }
      }
      const hashIdx = uri.lastIndexOf("#");
      if (hashIdx > 0) return uri.substring(0, hashIdx);
      const slashIdx = uri.lastIndexOf("/");
      return slashIdx > 0 ? uri.substring(0, slashIdx) : uri;
    }
    const cells: Map<string, OntologyAlignment[]> = new Map();
    for (const alignment of alignments) {
      const key = `${ontologyOfUri(alignment.source_uri)}|||${ontologyOfUri(alignment.target_uri)}`;
      const bucket = cells.get(key) ?? [];
      bucket.push(alignment);
      cells.set(key, bucket);
    }
    return { ontologies: registry, cells };
  }, [registry, alignments]);

  const handleSave = useCallback(async () => {
    if (!sourceUri.trim() || !targetUri.trim()) {
      setError(copy.missing_uris);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const saved = await saveAlignment(
        workspaceId,
        {
          source_uri: sourceUri.trim(),
          target_uri: targetUri.trim(),
          relation,
          confidence,
          provenance: provenance || undefined,
          source: source || undefined,
          reviewer: reviewer || undefined,
        },
        { locale: apiLocale },
      );
      setSourceUri("");
      setTargetUri("");
      setEditorOpen(false);
      if (saved && typeof saved === "object" && "status" in saved && saved.status === "proposed") {
        await reload();
        toast.success(copy.toast_proposed, {
          action: {
            label: copy.toast_review_action,
            onClick: () => navigate(workspaceReviewPath(workspaceId)),
          },
        });
      } else {
        await reload();
        toast.success(copy.toast_saved);
      }
    } catch (err) {
      setError(wsApiErrorMessage(err, apiLocale));
    } finally {
      setBusy(false);
    }
  }, [
    apiLocale,
    copy.missing_uris,
    copy.toast_saved,
    copy.toast_proposed,
    copy.toast_review_action,
    workspaceId,
    sourceUri,
    targetUri,
    relation,
    confidence,
    provenance,
    source,
    reviewer,
    reload,
    navigate,
  ]);

  const handleSuggest = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const data = await suggestAlignments(
        workspaceId,
        {
          source_ontology_uri: sourceOntology || undefined,
          target_ontology_uri: targetOntology || undefined,
          threshold,
          limit: 40,
        },
        { locale: apiLocale },
      );
      setSuggestions(data);
    } catch (err) {
      setError(wsApiErrorMessage(err, apiLocale));
    } finally {
      setBusy(false);
    }
  }, [apiLocale, workspaceId, sourceOntology, targetOntology, threshold]);

  const handleAcceptSuggestion = useCallback((suggestion: AlignmentSuggestion) => {
    setSourceUri(suggestion.source_uri);
    setTargetUri(suggestion.target_uri);
    setRelation(suggestion.relation);
    setConfidence(Math.max(0.1, Math.min(1, suggestion.score)));
    setProvenance(suggestion.reason);
    setEditorOpen(true);
    setSuggestOpen(false);
  }, []);

  const handleRemove = useCallback(async (id: string) => {
    setBusy(true);
    setError("");
    try {
      const removed = await removeAlignment(workspaceId, id, { locale: apiLocale });
      await reload();
      if (removed?.status === "proposed") {
        toast.success(copy.toast_delete_proposed, {
          action: {
            label: copy.toast_review_action,
            onClick: () => navigate(workspaceReviewPath(workspaceId)),
          },
        });
      }
    } catch (err) {
      setError(wsApiErrorMessage(err, apiLocale));
    } finally {
      setBusy(false);
    }
  }, [apiLocale, workspaceId, reload, navigate, copy.toast_delete_proposed, copy.toast_review_action]);

  function openAlignment(item: OntologyAlignment) {
    setSourceUri(item.source_uri);
    setTargetUri(item.target_uri);
    setRelation(item.relation);
    setConfidence(item.confidence);
    setProvenance(item.provenance ?? "");
    setEditorOpen(true);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      <section className="flex min-h-0 flex-[1.15] flex-col overflow-hidden rounded-lg border border-border">
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
          <PublicIcon name="git-merge" size={13} className="shrink-0 text-muted-foreground" />
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{copy.matrix}</span>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{matrix.ontologies.length}</span>
          <div className="ml-auto flex items-center gap-1">
            <Button type="button" size="sm" variant="outline" className="h-8 px-2 text-xs" onClick={() => setSuggestOpen(true)}>
              <PublicIcon name="stars" size={14} />
              {copy.suggest}
            </Button>
            <Button type="button" size="sm" className="h-8 px-2 text-xs" onClick={() => setEditorOpen(true)}>
              <PublicIcon name="plus-01" size={14} />
              {copy.new_alignment}
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {matrix.ontologies.length >= 2 ? (
            <div className={ontAlignMatrixWrap}>
              <table className={ontAlignMatrixTable}>
                <thead>
                  <tr>
                    <th className={ontAlignMatrixCorner} />
                    {matrix.ontologies.map((col) => (
                      <th key={col.uri} className={ontAlignMatrixColHeader}>{col.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix.ontologies.map((row) => (
                    <tr key={row.uri}>
                      <td className={ontAlignMatrixRowHeader}>{row.name}</td>
                      {matrix.ontologies.map((col) => {
                        const key = `${row.uri}|||${col.uri}`;
                        const cellItems = matrix.cells.get(key) ?? [];
                        const isDiag = row.uri === col.uri;
                        return (
                          <td key={col.uri} className={cn(ontAlignMatrixCell, isDiag && ontAlignMatrixCellDiag)}>
                            {isDiag ? <span className="text-muted-foreground">—</span> : cellItems.length ? (
                              <div className="flex flex-col gap-1">
                                {cellItems.map((item) => (
                                  <span
                                    key={item.id}
                                    role="button"
                                    tabIndex={0}
                                    className={cn(ontAlignRelationBadge, relationBadgeClass(item.relation))}
                                    title={`${item.source_label} → ${item.target_label} (${Math.round(item.confidence * 100)}%)`}
                                    onClick={() => openAlignment(item)}
                                    onKeyDown={(event) => {
                                      if (event.key === "Enter" || event.key === " ") openAlignment(item);
                                    }}
                                  >
                                    {alignmentRelationLabel(copy, item.relation)}
                                  </span>
                                ))}
                              </div>
                            ) : <span className="text-xs text-muted-foreground/30">·</span>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <QuietEmpty icon="git-merge" title={copy.empty_matrix_title} body={copy.empty_matrix_body} />
          )}
        </div>
        <p className="shrink-0 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
          {matrix.ontologies.length >= 2 ? `${copy.click_hint} ` : null}
          {copy.ephemeral}
        </p>
      </section>

      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border">
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
          <PublicIcon name="list-dashes-01" size={13} className="shrink-0 text-muted-foreground" />
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{copy.recorded}</span>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{alignments.length}</span>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {alignments.length === 0 ? (
            <QuietEmpty icon="git-merge" title={copy.empty_recorded_title} body={copy.empty_recorded_body} />
          ) : (
            alignments.map((item) => (
              <div key={item.id} className="flex items-center gap-3 border-b border-border px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] text-foreground">{item.source_label || item.source_uri}</p>
                  <p className="truncate font-mono text-[11px] text-muted-foreground">{item.source_uri}</p>
                </div>
                <span className={cn(ontAlignRelationBadge, relationBadgeClass(item.relation))}>
                  {alignmentRelationLabel(copy, item.relation)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] text-foreground">{item.target_label || item.target_uri}</p>
                  <p className="truncate font-mono text-[11px] text-muted-foreground">{item.target_uri}</p>
                </div>
                <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">{Math.round(item.confidence * 100)}%</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-8 shrink-0 text-destructive hover:text-destructive"
                  disabled={busy}
                  title={copy.remove}
                  onClick={() => void handleRemove(item.id)}
                >
                  <PublicIcon name="trash-01" size={14} />
                </Button>
              </div>
            ))
          )}
        </div>
      </section>

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="max-h-[min(92vh,36rem)] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{copy.editor_title}</DialogTitle>
            <DialogDescription>{copy.editor_body}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>{copy.source_uri}</Label>
              <Input value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>{copy.target_uri}</Label>
              <Input value={targetUri} onChange={(event) => setTargetUri(event.target.value)} />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{copy.relation}</Label>
                <Select
                  value={relation}
                  onValueChange={(value) => setRelation(value as AlignmentRelation)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {RELATIONS.map((item) => (
                      <SelectItem key={item} value={item}>
                        {alignmentRelationLabel(copy, item)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>
                  {copy.confidence} {formatLocaleFixedDecimals(locale, confidence, 2)}
                </Label>
                <Slider
                  min={0}
                  max={1}
                  step={0.01}
                  value={[confidence]}
                  onValueChange={(value) => setConfidence(value[0] ?? 0)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>{copy.provenance}</Label>
              <Textarea
                className="min-h-[74px] resize-y"
                value={provenance}
                onChange={(event) => setProvenance(event.target.value)}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>{copy.source}</Label>
                <Input value={source} onChange={(event) => setSource(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>{copy.reviewer}</Label>
                <Input value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
              </div>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:justify-end">
            <Button type="button" variant="outline" onClick={() => setEditorOpen(false)}>
              {t.core.common.cancel}
            </Button>
            <Button type="button" disabled={busy} onClick={() => void handleSave()}>
              {busy ? <PublicIcon name="loader-01" size={14} className="animate-spin" /> : <PublicIcon name="git-merge" size={14} />}
              {busy ? copy.saving : copy.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={suggestOpen} onOpenChange={setSuggestOpen}>
        <DialogContent
          className="max-h-[min(92vh,40rem)] max-w-lg overflow-y-auto"
          data-testid="vocabulary-alignment-suggest-dialog"
        >
          <DialogHeader>
            <DialogTitle>{copy.suggest_title}</DialogTitle>
            <DialogDescription>{copy.suggest_body}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>{copy.source_ontology}</Label>
              <div className="native-select--full">
                <NativeSelect
                  value={sourceOntology}
                  onChange={(event) => setSourceOntology(event.target.value)}
                  data-testid="vocabulary-alignment-suggest-source"
                >
                  <NativeSelectOption value="">{copy.any_ontology}</NativeSelectOption>
                  {registry.map((entry) => (
                    <NativeSelectOption key={entry.uri} value={entry.uri}>
                      {entry.name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>
            </div>
            <div className="space-y-2">
              <Label>{copy.target_ontology}</Label>
              <div className="native-select--full">
                <NativeSelect
                  value={targetOntology}
                  onChange={(event) => setTargetOntology(event.target.value)}
                >
                  <NativeSelectOption value="">{copy.any_ontology}</NativeSelectOption>
                  {registry.map((entry) => (
                    <NativeSelectOption key={entry.uri} value={entry.uri}>
                      {entry.name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            <Label>
              {copy.threshold} {formatLocaleFixedDecimals(locale, threshold, 2)}
            </Label>
            <Slider
              min={0.25}
              max={0.95}
              step={0.01}
              value={[threshold]}
              onValueChange={(value) => setThreshold(value[0] ?? 0.25)}
            />
          </div>
          <Button type="button" className="mt-3" variant="outline" disabled={busy} onClick={() => void handleSuggest()}>
            <PublicIcon name="stars" size={14} className="mr-1" />
            {copy.run_suggest}
          </Button>
          <div className={ontAlignSuggestList}>
            {suggestions.map((item) => (
              <Button
                type="button"
                key={`${item.source_uri}-${item.target_uri}-${item.relation}`}
                variant="outline"
                className={cn(govOhSuggestion, "h-auto w-full flex-wrap justify-start py-2 font-normal")}
                onClick={() => handleAcceptSuggestion(item)}
              >
                <span className={ontStrong}>{item.source_label}</span>
                <span className={relationBadgeClass(item.relation)}>
                  {alignmentRelationLabel(copy, item.relation)}
                </span>
                <span className={ontStrong}>{item.target_label}</span>
                <span className={govOhMuted}>{Math.round(item.score * 100)}%</span>
              </Button>
            ))}
            {!suggestions.length ? <p className="text-[11px] text-muted-foreground">{copy.suggest_empty}</p> : null}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function QuietEmpty({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="flex h-full min-h-32 flex-col items-center justify-center px-6 text-center">
      <PublicIcon name={icon} size={18} className="mb-2 text-muted-foreground" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-sm text-[11px] leading-snug text-muted-foreground">{body}</p>
    </div>
  );
}

