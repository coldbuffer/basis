import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useCallback, useEffect, useState, useRef } from "react";
import Editor, { useMonaco } from "@monaco-editor/react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog.js";
import { Button } from "@/components/ui/button.js";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleNumber, pickCountForm, requestFailedStatusMessage } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import type { LocaleMessages } from "@/i18n/en.js";
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { errorFromApiResponse } from "@/lib/errors/api-error.js";
import { useApiErrorMessage } from "@/lib/errors/use-api-error-message.js";
import { useTheme } from "@/lib/shell/theme.js";
import { cn } from "@/lib/utils.js";
import {
  exWsDataTable,
  exWsErrorBanner,
  exWsHint,
  exWsNullCell,
  exWsPageRow,
  exWsScrollFill,
  exWsSkeletonRow,
  exWsSkeletonStack,
  exWsSplitMain,
  exWsSplitSidebar,
  exWsTableWrap,
  exWsTd,
  exWsTdIndex,
  exWsTh,
  exWsThIndex,
  exWsTr,
  exWsUriCell,
  exWsTemplateSegmentBtn,
  exWsTemplateSegmentBtnActive,
  exWsTemplateSegmentGroup,
} from "@/lib/ui-classes/ws-ui.js";

type SparqlTemplateId = keyof LocaleMessages['analyze']['sparql']['template_labels'];

const TEMPLATES: { id: SparqlTemplateId; icon: string; query: string }[] = [
  { id: "triples", icon: "table", query: "SELECT ?s ?p ?o\nWHERE {\n  ?s ?p ?o\n}\nLIMIT 20" },
  { id: "types", icon: "tag", query: "SELECT ?type (COUNT(?s) AS ?count)\nWHERE {\n  ?s a ?type\n}\nGROUP BY ?type\nORDER BY DESC(?count)" },
  { id: "edges", icon: "git-branch-01", query: "SELECT ?predicate ?object\nWHERE {\n  <urn:node:example> ?predicate ?object\n}\nLIMIT 50" },
  { id: "path", icon: "path", query: "SELECT ?mid ?p1 ?p2\nWHERE {\n  <urn:node:a> ?p1 ?mid .\n  ?mid ?p2 <urn:node:b>\n}\nLIMIT 20" },
];

export function SparqlScreen({ workspaceId }: { workspaceId: string }) {
  const { t, locale } = useI18n();
  const copy = t.analyze.sparql;
  const rowCountLabel = (n: number) =>
    fmt(pickCountForm(locale, n, copy.rows_one, copy.rows), { count: formatLocaleNumber(locale, n) });
  const { theme } = useTheme();
  const apiError = useApiErrorMessage();
  const monaco = useMonaco();
  const editorRef = useRef<unknown>(null);
  const [query, setQuery] = useState(TEMPLATES[0].query);
  const [result, setResult] = useState<{ columns?: string[]; rows?: Record<string, string>[]; error?: string; error_line?: number } | null>(null);
  const [error, setError] = useState("");
  const [runSnapshot, setRunSnapshot] = useState<string | null>(null);
  const [pendingQuery, setPendingQuery] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [copyState, setCopyState] = useState(false);

  function handleEditorWillMount(monacoIns: {
    languages: {
      getLanguages(): { id: string }[];
      register(opts: { id: string }): void;
      setMonarchTokensProvider(id: string, p: unknown): void;
    };
    editor: { defineTheme(id: string, t: unknown): void };
  }) {
    if (!monacoIns.languages.getLanguages().some((l) => l.id === "sparql")) {
      monacoIns.languages.register({ id: "sparql" });
      monacoIns.languages.setMonarchTokensProvider("sparql", {
        keywords: ["SELECT", "WHERE", "LIMIT", "FILTER", "OPTIONAL", "PREFIX", "ORDER", "BY", "DESC", "ASC", "GROUP", "DISTINCT", "CONSTRUCT", "ASK", "DESCRIBE"],
        tokenizer: {
          root: [
            [/[a-zA-Z_]\w*/, { cases: { "@keywords": "keyword", "@default": "identifier" } }],
            [/[?$][a-zA-Z_]\w*/, "variable.name"],
            [/<[^>]+>/, "string.uri"],
            [/"[^"]*"/, "string"],
            [/#.*/, "comment"],
            [/[0-9]+(\.[0-9]+)?/, "number"],
          ],
        },
      });
    }
  }

  function handleEditorDidMount(editor: unknown) {
    editorRef.current = editor;
  }

  const editorTheme = theme === "dark" ? "vs-dark" : "vs";

  const handleRun = useCallback(async () => {
    if (isLoading || !query.trim()) return;
    setIsLoading(true);
    setError("");
    const snapshot = query;
    if (monaco && editorRef.current) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (monaco as any).editor.setModelMarkers((editorRef.current as any).getModel(), "sparql", []);
    }
    try {
      const res = await workspaceOpenApiResponse('POST', workspaceId, 'sparql', {
        body: { query },
      });
      if (!res.headers.get("content-type")?.includes("application/json")) {
        const text = await res.text();
        throw errorFromApiResponse(
          res.status,
          { detail: { message: text.substring(0, 200) } },
          requestFailedStatusMessage(locale as Locale, res.status),
          locale as Locale,
        );
      }
      const data = await res.json();
      if (!res.ok) {
        throw errorFromApiResponse(
          res.status,
          data,
          requestFailedStatusMessage(locale as Locale, res.status),
          locale as Locale,
        );
      }
      if (res.status === 207) {
        data.error = data.message || copy.partial_query;
      }
      setRunSnapshot(snapshot);

      if (data.error && data.error_line && monaco && editorRef.current) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (monaco as any).editor.setModelMarkers((editorRef.current as any).getModel(), "sparql", [{
          startLineNumber: data.error_line,
          startColumn: data.error_column || 1,
          endLineNumber: data.error_line,
          endColumn: 100,
          message: data.error,
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          severity: (monaco as any).MarkerSeverity.Error,
        }]);
      }
      setResult(data);
      setError(typeof data.error === "string" ? data.error : "");
    } catch (e) {
      setError(apiError(e));
    } finally {
      setIsLoading(false);
    }
  }, [apiError, isLoading, workspaceId, locale, monaco, query]);

  const handleCopyQuery = useCallback(() => {
    navigator.clipboard.writeText(query).then(() => {
      setCopyState(true);
      setTimeout(() => setCopyState(false), 1500);
    }).catch(() => {
      /* Clipboard unavailable */
    });
  }, [query]);

  const handleExportCSV = useCallback(() => {
    if (!result?.rows || !result?.columns) return;
    const cols = result.columns;
    const header = cols.join(",");
    const rows = result.rows.map((r) => cols.map((c) => JSON.stringify(r[c] ?? "")).join(",")).join("\n");
    const blob = new Blob([`${header}\n${rows}`], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sparql_results.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [result?.columns, result?.rows]);

  const canExportCsv = Boolean(result?.rows && result.rows.length > 0 && result?.columns);
  const resultStale = Boolean(result && runSnapshot !== null && runSnapshot !== query);

  const applyTemplate = useCallback((nextQuery: string) => {
    setQuery(nextQuery);
    setPendingQuery(null);
  }, []);

  const requestTemplate = useCallback((nextQuery: string) => {
    if (query === nextQuery) return;
    const untouched = !query.trim() || TEMPLATES.some((template) => template.query === query);
    if (untouched) {
      applyTemplate(nextQuery);
      return;
    }
    setPendingQuery(nextQuery);
  }, [applyTemplate, query]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key !== "Enter") return;
      const target = event.target;
      if (target instanceof HTMLElement && target.closest("[role='dialog']")) return;
      event.preventDefault();
      void handleRun();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleRun]);

  return (
    <div className={exWsPageRow}>
      <div className={exWsSplitSidebar}>
        <div className="flex h-12 shrink-0 items-center justify-between gap-2 border-b border-border px-4">
          <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
            <PublicIcon name="file-code" size={13} />
            {copy.templates}
          </span>
          <div className={exWsTemplateSegmentGroup} role="group" aria-label={copy.templates}>
            {TEMPLATES.map((template) => {
              const active = query === template.query;
              return (
                <Button
                  key={template.id}
                  type="button"
                  variant="ghost"
                  size="sm"
                  className={cn(exWsTemplateSegmentBtn, active && exWsTemplateSegmentBtnActive)}
                  onClick={() => requestTemplate(template.query)}
                >
                  <PublicIcon name={template.icon} size={12} />
                  {copy.template_labels[template.id]}
                </Button>
              );
            })}
          </div>
        </div>

        <div className="min-h-48 flex-1">
          <Editor
            height="100%"
            defaultLanguage="sparql"
            theme={editorTheme}
            value={query}
            onChange={(v) => setQuery(v || "")}
            beforeMount={handleEditorWillMount}
            onMount={handleEditorDidMount}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              fontFamily: "'JetBrains Mono','Fira Code',Consolas,monospace",
              lineHeight: 22,
              padding: { top: 12 },
              scrollBeyondLastLine: false,
              renderLineHighlight: "gutter",
              wordWrap: "on",
            }}
          />
        </div>

        <div className="flex h-12 shrink-0 items-center gap-2 border-t border-border px-4">
          <Button type="button" size="sm" variant="outline" className="h-8 px-2 text-xs" onClick={handleCopyQuery}>
            <PublicIcon name="copy-left" size={14} />
            {copyState ? t.core.common.copySuccess : t.core.common.copy}
          </Button>
          <Button
            type="button"
            size="sm"
            className="ml-auto h-8"
            onClick={() => void handleRun()}
            disabled={isLoading || !query.trim()}
          >
            {isLoading ? <PublicIcon name="loader-01" size={14} className="animate-spin" /> : <PublicIcon name="play-03" size={14} />}
            {isLoading ? copy.running : copy.run}
          </Button>
        </div>
      </div>

      <div className={exWsSplitMain}>
        <div className="flex h-12 shrink-0 items-center gap-3 border-b border-border px-4">
          <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
            <PublicIcon name="table" size={13} />
            {copy.results}
          </span>
          {result?.rows ? (
            <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{rowCountLabel(result.rows.length)}</span>
          ) : null}
          {canExportCsv ? (
            <Button type="button" size="sm" variant="outline" className="ml-auto h-8 shrink-0 px-2 text-xs" onClick={handleExportCSV}>
              <PublicIcon name="download-01" size={14} />
              {copy.export_csv}
            </Button>
          ) : null}
        </div>

        <div className={exWsScrollFill}>
          {isLoading ? (
            <div className={exWsSkeletonStack}>
              {[1, 2, 3].map((i) => <div key={i} className={exWsSkeletonRow} />)}
            </div>
          ) : null}

          {error && !isLoading ? (
            <div className={exWsErrorBanner}>
              <PublicIcon name="alert-circle" size={16} className="mt-0.5 shrink-0" />
              {error}
            </div>
          ) : null}

          {resultStale && !isLoading ? (
            <p className={`${exWsHint} flex items-center gap-1.5 px-4 pt-3`}>
              <PublicIcon name="clock-backward" size={13} />
              {copy.stale}
            </p>
          ) : null}

          {result?.rows && result?.columns && !isLoading ? (
            <div className={exWsTableWrap}>
              {result.rows.length === 0 ? (
                <p className="px-4 py-6 text-sm text-muted-foreground">{copy.no_rows}</p>
              ) : (
                <table className={exWsDataTable}>
                  <thead>
                    <tr className="border-b border-border bg-muted/30">
                      <th className={exWsThIndex}>#</th>
                      {result.columns.map((c) => (
                        <th key={c} className={exWsTh}>?{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((r, i) => (
                      <tr key={i} className={exWsTr}>
                        <td className={exWsTdIndex}>{i + 1}</td>
                        {(result.columns ?? []).map((c) => (
                          <td key={c} className={exWsTd} title={String(r[c] ?? "")}>
                            {r[c] != null ? (
                              String(r[c]).startsWith("urn:") || String(r[c]).startsWith("http")
                                ? <span className={exWsUriCell}>{String(r[c])}</span>
                                : String(r[c])
                            ) : <span className={exWsNullCell}>null</span>}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ) : null}

          {!result && !isLoading && !error ? (
            <div className="flex h-full flex-col items-center justify-center px-6 text-center">
              <PublicIcon name="table" size={18} className="mb-2 text-muted-foreground" />
              <p className="text-sm font-medium text-foreground">{copy.empty_title}</p>
              <p className={`${exWsHint} mt-1 max-w-xs`}>
                {query.trim() ? copy.empty_ready : copy.empty_body}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <AlertDialog open={pendingQuery !== null} onOpenChange={(open) => { if (!open) setPendingQuery(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{copy.replace_title}</AlertDialogTitle>
            <AlertDialogDescription>{copy.replace_body}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t.core.common.cancel}</AlertDialogCancel>
            <AlertDialogAction onClick={() => { if (pendingQuery) applyTemplate(pendingQuery); }}>
              {copy.replace_confirm}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
