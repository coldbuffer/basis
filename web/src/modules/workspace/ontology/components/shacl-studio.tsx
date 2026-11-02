import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useCallback, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/utils.js";
import Editor, { type Monaco } from "@monaco-editor/react";
import { Button } from "@/components/ui/button.js";
import {
  NativeSelect,
  NativeSelectOption,
} from "@/components/ui/native-select.js";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleNumber, pickCountForm } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { useTheme } from "@/lib/shell/theme.js";
import { exWsHint, exWsScrollFill, exWsSplitMain, exWsSplitSidebar } from "@/lib/ui-classes/ws-ui.js";
import {
  generateShacl,
  loadOntologyRegistry,
  loadShaclShapes,
  saveGovernanceShacl,
  validateShacl,
} from '../lib/api.js';
import { toast } from 'sonner';
import { useOntologyWorkspaceId } from '@/components/app/shared/workspace/ontology-workspace-context.js';
import { wsApiErrorMessage } from '@/lib/workspace/ws-api-error';
import type { OntologyEntry, ShaclShapeSummary, ShaclValidationResponse } from '../lib/types.js';

function localName(value: string): string {
  const cut = Math.max(value.lastIndexOf("#"), value.lastIndexOf("/"));
  const name = cut >= 0 ? value.slice(cut + 1) : value;
  return name || value;
}

interface ShaclStudioProps {
  onJumpToNode?: (nodeId: string) => void;
  /** Deep-link from data quality or review (`?ontology_uri=`). */
  initialOntologyUri?: string | null;
}

export function ShaclStudio({ onJumpToNode, initialOntologyUri }: ShaclStudioProps) {
  const workspaceId = useOntologyWorkspaceId();
  const { t, locale } = useI18n();
  const copy = t.ontology.shacl;
  const constraintsLabel = (n: number) =>
    fmt(pickCountForm(locale, n, copy.constraints_one, copy.constraints), {
      count: formatLocaleNumber(locale, n),
    });
  const { theme } = useTheme();
  const [registry, setRegistry] = useState<OntologyEntry[]>([]);
  const [selectedUri, setSelectedUri] = useState("");
  const [shacl, setShacl] = useState("");
  const [fullShacl, setFullShacl] = useState("");
  const [shapes, setShapes] = useState<ShaclShapeSummary[]>([]);
  const [selectedShapeId, setSelectedShapeId] = useState<string | null>(null);
  const [validation, setValidation] = useState<ShaclValidationResponse | null>(null);
  const [shapeSource, setShapeSource] = useState<"saved" | "generated" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadOntologyRegistry(workspaceId, { locale: locale as Locale })
      .then((entries) => {
        if (cancelled) return;
        setRegistry(entries);
        const preferred = initialOntologyUri?.trim();
        const match = preferred && entries.some((e) => e.uri === preferred) ? preferred : '';
        setSelectedUri((current) => current || match || entries[0]?.uri || "");
      })
      .catch((err) => {
        if (cancelled) return;
        setError(wsApiErrorMessage(err, locale as Locale));
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, initialOntologyUri]);

  const [prevUri, setPrevUri] = useState(selectedUri);
  if (selectedUri !== prevUri) {
    setPrevUri(selectedUri);
    setShacl("");
    setFullShacl("");
    setSelectedShapeId(null);
    setValidation(null);
    setLoading(true);
    setError("");
  }

  useEffect(() => {
    let ignore = false;
    async function fetchShapes() {
      if (!selectedUri) return;
      try {
        const data = await loadShaclShapes(workspaceId, selectedUri, { locale: locale as Locale });
        if (!ignore) {
          setShapes(data.shapes);
          const turtle = data.shacl_turtle;
          setFullShacl(turtle);
          setShacl((current) => current || turtle);
          setShapeSource(data.source ?? null);
          setSelectedShapeId(null);
          setValidation(null);
        }
      } catch (err) {
        if (!ignore) {
          setShapes([]);
          setFullShacl("");
          setShacl("");
          setError(wsApiErrorMessage(err, locale as Locale));
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }
    void fetchShapes();
    return () => {
      ignore = true;
    };
  }, [workspaceId, selectedUri]);

  const handleGenerate = useCallback(async () => {
    if (!selectedUri) return;
    setLoading(true);
    setError("");
    try {
      const data = await generateShacl(workspaceId, selectedUri, "strict", { locale: locale as Locale });
      setFullShacl(data.shacl_turtle);
      setShacl(data.shacl_turtle);
      setSelectedShapeId(null);
      const shapeData = await loadShaclShapes(workspaceId, selectedUri, { locale: locale as Locale });
      setShapes(shapeData.shapes);
      setShapeSource("generated");
      setValidation(null);
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, selectedUri]);

  const handleSaveForScan = async () => {
    if (!selectedUri || !shacl.trim()) return;
    setLoading(true);
    setError("");
    try {
      await saveGovernanceShacl(workspaceId, selectedUri, fullShacl || shacl, { locale: locale as Locale });
      setShapeSource("saved");
      toast.success(copy.save_success);
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectShape = useCallback((shapeId: string) => {
    setSelectedShapeId(shapeId);
    const src = fullShacl || shacl;
    const normalised = src.replace(/\r\n/g, "\n");
    const blocks = normalised.split(/\n{2,}/).filter((b) => b.trim());
    const match = blocks.find((b) => {
      const first = b.trimStart();
      return first.startsWith(shapeId + " ") || first.startsWith(shapeId + "\n") || first.startsWith(shapeId + "\t");
    });
    if (match) {
      setShacl(match.trim());
    }
  }, [fullShacl, shacl]);

  const handleShowAllShapes = useCallback(() => {
    setSelectedShapeId(null);
    setShacl(fullShacl);
  }, [fullShacl]);

  const handleValidate = async () => {
    if (!selectedUri || !shacl.trim()) return;
    setLoading(true);
    setError("");
    try {
      setValidation(await validateShacl(workspaceId, selectedUri, shacl, { locale: locale as Locale }));
    } catch (err) {
      setError(wsApiErrorMessage(err, locale as Locale));
    } finally {
      setLoading(false);
    }
  };

  const groupedShapes = useMemo(() => {
    const groups = new Map<string, ShaclShapeSummary[]>();
    for (const shape of shapes) {
      const key = shape.target_class || "";
      groups.set(key, [...(groups.get(key) || []), shape]);
    }
    return Array.from(groups.entries());
  }, [shapes]);

  const beforeMount = useCallback((monaco: Monaco) => {
    try {
      if (!monaco.languages.getLanguages().some((language: { id: string }) => language.id === "turtle")) {
        monaco.languages.register({ id: "turtle", extensions: [".ttl"], mimetypes: ["text/turtle"] });
        monaco.languages.setMonarchTokensProvider("turtle", {
          tokenizer: {
            root: [
              [/#[^\n]*/, "comment"],
              [/"(?:[^"\\]|\\.)*"/, "string"],
              [/'(?:[^'\\]|\\.)*'/, "string"],
              [/"""[\s\S]*?"""/, "string"],
              [/<[^>]*>/, "type.identifier"],
              [/[@](?:prefix|base)\b/, "keyword"],
              [/\ba\b/, "keyword"],
              [/\b(?:sh|xsd|owl|rdf|rdfs|skos):[\w]+/, "variable"],
              [/[a-zA-Z_][\w-]*:[\w]+/, "namespace"],
              [/[;,.]/, "delimiter"],
              [/\d+(?:\.\d+)?/, "number"],
            ],
          },
        });
      }
    } catch {
      /* Monaco setup failure should not crash the component */
    }
  }, []);

  const editorTheme = theme === "dark" ? "vs-dark" : "vs";

  const statusLabel = validation
    ? validation.status === "unavailable"
      ? copy.unavailable
      : validation.conforms
        ? copy.conforms
        : validation.status
    : null;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-4">
        <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          <PublicIcon name="shield-01" size={13} />
          SHACL
        </span>
        <label className="sr-only" htmlFor="shacl-ontology">{copy.ontology}</label>
        <div className="native-select--full min-w-0 max-w-sm flex-1">
          <NativeSelect
            id="shacl-ontology"
            size="sm"
            className="text-xs"
            value={selectedUri}
            onChange={(event) => setSelectedUri(event.target.value)}
          >
            {registry.map((entry) => (
              <NativeSelectOption key={entry.uri} value={entry.uri}>
                {entry.name}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
        <span className="hidden font-mono text-[11px] text-muted-foreground sm:inline">
          {shapes.length}
        </span>
        {shapeSource ? (
          <span className="hidden text-[11px] text-muted-foreground sm:inline" data-testid="shacl-shape-source">
            {shapeSource === "saved" ? copy.source_saved : copy.source_generated}
          </span>
        ) : null}
        <Button type="button" size="sm" variant="outline" className="h-8" disabled={loading || !selectedUri} onClick={() => void handleGenerate()}>
          <PublicIcon name="magic-wand" size={14} />
          {copy.generate}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          className="h-8"
          disabled={loading || !selectedUri || !shacl.trim()}
          onClick={() => void handleSaveForScan()}
          data-testid="shacl-save-for-scan"
        >
          {loading ? copy.saving : copy.save_for_scan}
        </Button>
        <Button type="button" size="sm" className="h-8" disabled={loading || !shacl.trim()} onClick={() => void handleValidate()}>
          <PublicIcon name={loading ? "loader-01" : "play-03"} size={14} className={loading ? "animate-spin" : undefined} />
          {loading ? copy.validating : copy.validate}
        </Button>
      </div>

      {error ? (
        <div className="flex shrink-0 items-start gap-2 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <PublicIcon name="alert-circle" size={16} className="mt-0.5" />
          <div>{error}</div>
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside className={cn(exWsSplitSidebar, "w-[min(320px,36vw)]")}>
          <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
            <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              <PublicIcon name="shapes-01" size={13} />
              {copy.shapes}
            </span>
            {selectedShapeId ? (
              <Button type="button" size="sm" variant="ghost" className="h-7 px-2 text-[11px]" onClick={handleShowAllShapes}>
                {copy.view_all}
              </Button>
            ) : null}
          </div>
          <div className={cn(exWsScrollFill, "flex flex-col gap-4 px-3 py-3")}>
            {groupedShapes.map(([target, items]) => (
              <div key={target} className="flex flex-col gap-1">
                <div className="truncate px-1 text-[10px] font-semibold tracking-wide text-muted-foreground uppercase" title={target || copy.untargeted}>
                  {target ? localName(target) : copy.untargeted}
                </div>
                {items.map((shape) => {
                  const isSelected = selectedShapeId === shape.id;
                  return (
                    <Button
                      key={shape.id}
                      type="button"
                      variant="ghost"
                      className={cn(
                        "h-auto w-full items-start justify-start gap-2 rounded-md px-2 py-1.5 text-left font-normal hover:bg-muted/60",
                        isSelected && "bg-muted",
                      )}
                      onClick={() => handleSelectShape(shape.id)}
                      title={shape.id}
                    >
                      <PublicIcon name="file-code" size={13} className={cn("mt-0.5", isSelected ? "text-foreground" : "text-muted-foreground")} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-xs font-medium text-foreground">{localName(shape.id)}</span>
                        <span className={cn(exWsHint, "block truncate")}>
                          {constraintsLabel(shape.constraint_count)}
                          {shape.constraints.length ? ` · ${shape.constraints.map(localName).join(", ")}` : ""}
                        </span>
                      </span>
                      {shape.violation_count > 0 ? (
                        <span className="font-mono text-[11px] tabular-nums text-destructive">{shape.violation_count}</span>
                      ) : null}
                    </Button>
                  );
                })}
              </div>
            ))}
            {!shapes.length ? <p className={cn(exWsHint, "px-1 py-6 text-center")}>{copy.empty_shapes}</p> : null}
          </div>
        </aside>

        <section className={exWsSplitMain}>
          <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
            <PublicIcon name="code-01" size={13} className="text-muted-foreground" />
            <h2 className="min-w-0 truncate text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              {selectedShapeId ? localName(selectedShapeId) : copy.all_shapes}
            </h2>
          </div>
          <div className="min-h-0 flex-1">
            <Editor
              height="100%"
              language="turtle"
              theme={editorTheme}
              beforeMount={beforeMount}
              value={shacl}
              onChange={(value) => setShacl(value || "")}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: "JetBrains Mono, monospace",
                wordWrap: "on",
                scrollBeyondLastLine: false,
                padding: { top: 12, bottom: 12 },
              }}
            />
          </div>
          <div className={cn("shrink-0 border-t border-border", validation ? "max-h-[42%] overflow-auto" : "")}>
            <div className="flex h-12 items-center gap-3 px-4">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
                <PublicIcon name="shield-check" size={13} />
                {copy.report}
              </span>
              {statusLabel ? (
                <span className={cn("font-mono text-[11px]", validationBadgeClass(validation!.status, validation!.conforms))}>
                  {statusLabel}
                  {validation?.violations.length ? ` · ${validation.violations.length}` : ""}
                </span>
              ) : (
                <span className={exWsHint}>{copy.report_empty}</span>
              )}
              {validation?.message ? (
                <span className={cn(exWsHint, "min-w-0 flex-1 truncate")} title={validation.message}>{validation.message}</span>
              ) : null}
            </div>
            {validation?.violations.length ? (
              <ol className="m-0 divide-y divide-border border-t border-border">
                {validation.violations.map((violation, index) => {
                  const nodeId = violation.focus_node || violation.node;
                  return (
                    <li key={`${violation.node}-${violation.path}-${index}`} className="flex items-start gap-3 px-4 py-2.5">
                      <span className="w-5 shrink-0 pt-0.5 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
                        {index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="text-xs text-foreground">{violation.message}</div>
                        <div className={cn(exWsHint, "mt-0.5 truncate")} title={violation.path}>
                          {violation.severity}
                          {violation.path ? ` · ${localName(violation.path)}` : ""}
                        </div>
                        {nodeId ? (
                          <div className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground" title={nodeId}>
                            {localName(nodeId)}
                          </div>
                        ) : null}
                      </div>
                      {nodeId ? (
                        <Button type="button" size="sm" variant="ghost" className="h-7 shrink-0 px-2 text-[11px]" onClick={() => onJumpToNode?.(nodeId)}>
                          <PublicIcon name="graph" size={13} />
                          {copy.jump}
                        </Button>
                      ) : null}
                    </li>
                  );
                })}
              </ol>
            ) : validation ? (
              <p className={cn(exWsHint, "border-t border-border px-4 py-3")}>{copy.no_violations}</p>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}

function validationBadgeClass(status: string, conforms: boolean) {
  if (status === "unavailable") return "text-warn";
  if (conforms) return "text-ok";
  return "text-destructive";
}
