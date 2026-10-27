import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useState, useCallback, useEffect, useRef } from "react";
import { useDropzone } from "react-dropzone";
import { Button } from "@/components/ui/button.js";
import { Textarea } from "@/components/ui/textarea.js";
import { errorFromApiResponse } from "@/lib/errors/api-error.js";
import { formatUserFacingApiError } from "@/lib/errors/api-error-message.js";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleFixedDecimals } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import {
  workspaceOpenApiGET,
  workspaceOpenApiResponse,
} from '@/lib/openapi/client.js';
import { logEvent } from '@/modules/graph/lib/registry-store.js';
import { cn } from "@/lib/utils.js";
import {
  exWsCardTitleRow,
  exWsDropzone,
  exWsDropzoneActive,
  exWsHint,
  exWsImportCard,
  exWsImportGrid,
  exWsImportPage,
  exWsPageHero,
  exWsPageHeroIcon,
  exWsToast,
  exWsToastError,
  exWsToastStack,
  exWsToastSuccess,
} from "@/lib/ui-classes/ws-ui.js";
import {
  wsBody,
  wsLabel,
  wsPage,
  wsPillMono,
  wsScroll,
  wsTitle,
} from "@/lib/ui-classes/console-ws.js";
import {
  GRAPH_EXPORT_FORMATS,
  type GraphExportFormat,
  graphExportExtension,
} from "./graph-export-formats.js";
import {
  formatGraphExportNodeIds,
  parseGraphExportNodeIds,
} from "@/modules/graph/lib/parse-graph-export-node-ids.js";
import {
  buildGraphAuditPack,
  triggerJsonFileDownload,
} from "@/modules/graph/lib/graph-audit-pack.js";

interface Toast {
  id: number;
  type: "success" | "error";
  text: string;
  action?: { label: string; onClick: () => void };
}

type ExportScope = "full" | "subgraph";

export function ImportExportScreen({
  workspaceId,
  focusSection,
  seedNodeIds,
  onImportQueued,
  importQueuedActionLabel,
}: {
  workspaceId: string;
  focusSection?: "import" | "export";
  /** Pre-fill subgraph export (e.g. graph `focus` node). */
  seedNodeIds?: string[];
  onImportQueued?: () => void;
  importQueuedActionLabel?: string;
}) {
  const { t, locale } = useI18n();
  const ie = t.graph.import_export;
  const reviewLabel = importQueuedActionLabel ?? ie.open_review_queue;
  const importRef = useRef<HTMLDivElement>(null);
  const exportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!focusSection) return;
    const target = focusSection === "import" ? importRef.current : exportRef.current;
    target?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [focusSection]);
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [exportFormat, setExportFormat] = useState<GraphExportFormat>("json");
  const exportMeta =
    GRAPH_EXPORT_FORMATS.find((row) => row.format === exportFormat) ?? GRAPH_EXPORT_FORMATS[0];
  const [exportScope, setExportScope] = useState<ExportScope>(() =>
    seedNodeIds?.length ? "subgraph" : "full",
  );
  const [subgraphIdsText, setSubgraphIdsText] = useState(() =>
    seedNodeIds?.length ? formatGraphExportNodeIds(seedNodeIds) : "",
  );
  const [isExporting, setIsExporting] = useState(false);
  const [isAuditPackBusy, setIsAuditPackBusy] = useState(false);

  useEffect(() => {
    if (!seedNodeIds?.length) return;
    setExportScope("subgraph");
    setSubgraphIdsText(formatGraphExportNodeIds(seedNodeIds));
  }, [seedNodeIds]);
  const [toasts, setToasts] = useState<Toast[]>([]);

  function showToast(
    type: Toast["type"],
    text: string,
    action?: Toast["action"],
  ) {
    const id = Date.now();
    setToasts((p) => [...p, { id, type, text, action }]);
    setTimeout(() => setToasts((p) => p.filter((toast) => toast.id !== id)), 8000);
  }

  const onDrop = useCallback((accepted: File[]) => {
    const picked = accepted[0];
    if (picked) setFile(picked);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/json": [".json"], "text/csv": [".csv"] },
    maxFiles: 1,
  });

  async function handleImport() {
    if (!file) return;
    setIsUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await workspaceOpenApiResponse('POST', workspaceId, 'review/items/graph-import', {
        body: fd,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw errorFromApiResponse(res.status, data, ie.import_failed);
      }
      const reviewAction = onImportQueued
        ? { label: reviewLabel, onClick: onImportQueued }
        : undefined;
      showToast(
        "success",
        fmt(ie.import_success, { name: file.name }),
        reviewAction,
      );
      logEvent("review", fmt(ie.log_queued_import, { name: file.name }), { file: file.name });
      setFile(null);
    } catch (e: unknown) {
      showToast("error", formatUserFacingApiError(e, locale as Locale));
    } finally { setIsUploading(false); }
  }

  function resolvedExportNodeIds(): string[] | undefined | null {
    if (exportScope !== "subgraph") return undefined;
    const ids = parseGraphExportNodeIds(subgraphIdsText);
    if (ids.length === 0) {
      showToast("error", ie.subgraph_ids_required);
      return null;
    }
    return ids;
  }

  function buildExportPayload(format: GraphExportFormat, nodeIds?: string[]) {
    const body: { format: GraphExportFormat; node_ids?: string[] } = { format };
    if (nodeIds?.length) body.node_ids = nodeIds;
    return body;
  }

  async function handleExport() {
    const nodeIds = resolvedExportNodeIds();
    if (nodeIds === null) return;
    setIsExporting(true);
    try {
      const res = await workspaceOpenApiResponse('POST', workspaceId, 'export', {
        body: buildExportPayload(exportFormat, nodeIds),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw errorFromApiResponse(res.status, data, ie.export_failed);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `basis_graph_export.${graphExportExtension(exportFormat)}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast(
        "success",
        fmt(ie.export_success, { format: graphExportExtension(exportFormat) }),
      );
      logEvent(
        "export",
        fmt(ie.log_exported, { format: exportFormat.toUpperCase() }),
        { format: exportFormat },
      );
    } catch (e: unknown) {
      showToast("error", formatUserFacingApiError(e, locale as Locale));
    } finally { setIsExporting(false); }
  }

  async function handleAuditPack() {
    const nodeIds = resolvedExportNodeIds();
    if (nodeIds === null) return;
    setIsAuditPackBusy(true);
    try {
      const pack = await buildGraphAuditPack({
        workspaceId,
        nodeIds,
        postExport: (body) =>
          workspaceOpenApiResponse('POST', workspaceId, 'export', { body }),
        getAudit: async () =>
          workspaceOpenApiGET<{ events: unknown[] }>(workspaceId, 'audit/graph-mutations', {
            params: {
              query: { limit: 100, action_prefix: 'workspace.graph.' },
            },
          }),
        getProjection: async () => {
          try {
            return await workspaceOpenApiGET(workspaceId, 'graph/projection');
          } catch {
            return undefined;
          }
        },
      });
      triggerJsonFileDownload("basis_graph_audit_pack.json", pack);
      showToast("success", ie.audit_pack_success);
    } catch (e: unknown) {
      showToast("error", formatUserFacingApiError(e, locale as Locale));
    } finally {
      setIsAuditPackBusy(false);
    }
  }

  return (
    <div className={cn(wsPage, wsScroll)}>
      <div className={exWsImportPage}>
        <div className={exWsPageHero}>
          <div className={exWsPageHeroIcon}>
            <PublicIcon name="upload-01" size={20} />
          </div>
          <div>
            <h2 className={cn(wsTitle, "text-lg")}>{ie.page_title}</h2>
            <div className={cn(wsBody, "mt-0.5")}>{ie.page_subtitle}</div>
          </div>
        </div>

        <div className={exWsImportGrid}>
          <div ref={importRef} className={exWsImportCard}>
            <div className={exWsCardTitleRow}>
              <PublicIcon name="upload-01" size={16} className="text-primary" />
              {ie.import_card_title}
            </div>
            {workspaceId ? (
              <div className={exWsHint}>
                {ie.import_hint}
              </div>
            ) : null}

            <div
              {...getRootProps()}
              className={cn(exWsDropzone, isDragActive && exWsDropzoneActive)}
            >
              <input {...getInputProps()} />
              {file ? (
                <>
                  <PublicIcon name="file-01" size={40} className="text-ok" />
                  <div className="font-bold text-foreground">{file.name}</div>
                  <div className={cn(wsBody, "text-[11px]")}>
                    {fmt(ie.file_size_replace, {
                      size: formatLocaleFixedDecimals(locale as Locale, file.size / 1024, 1),
                    })}
                  </div>
                </>
              ) : (
                <>
                  <PublicIcon name="upload-01" size={36} className="text-primary opacity-70" />
                  <div className="font-semibold text-foreground">{ie.drop_browse}</div>
                  <div className={wsPillMono}>.json</div>
                  <span className={exWsHint}>{ie.or}</span>
                  <div className={wsPillMono}>.csv</div>
                </>
              )}
            </div>

            <Button
              type="button"
              className="w-full"
              onClick={handleImport}
              disabled={!file || isUploading}
            >
              {isUploading ? (
                <>
                  <PublicIcon name="loader-01" size={15} className="animate-spin" />
                  {ie.uploading}
                </>
              ) : (
                <>
                  <PublicIcon name="upload-01" size={15} />
                  {ie.upload_to_graph}
                </>
              )}
            </Button>
          </div>

          <div ref={exportRef} className={exWsImportCard}>
            <div className={exWsCardTitleRow}>
              <PublicIcon name="download-01" size={16} className="text-primary" />
              {ie.export_card_title}
            </div>

            <div>
              <label className={wsLabel}>{ie.export_scope_label}</label>
              <div className="mb-3 flex flex-wrap gap-2">
                {(
                  [
                    ["full", ie.export_scope_full],
                    ["subgraph", ie.export_scope_subgraph],
                  ] as const
                ).map(([scope, label]) => (
                  <Button
                    key={scope}
                    type="button"
                    variant={exportScope === scope ? "default" : "outline"}
                    className="flex-1 text-xs"
                    onClick={() => setExportScope(scope)}
                  >
                    {label}
                  </Button>
                ))}
              </div>
              {exportScope === "subgraph" ? (
                <div className="mb-3 space-y-1.5">
                  <label className={wsLabel} htmlFor="graph-export-node-ids">
                    {ie.subgraph_ids_label}
                  </label>
                  <Textarea
                    id="graph-export-node-ids"
                    className="min-h-[5.5rem] font-mono text-xs"
                    value={subgraphIdsText}
                    onChange={(event) => setSubgraphIdsText(event.target.value)}
                    data-testid="graph-export-node-ids"
                  />
                  <p className={cn(wsBody, "text-[11px] text-muted-foreground")}>{ie.subgraph_ids_hint}</p>
                </div>
              ) : null}
              <label className={wsLabel}>{ie.format_label}</label>
              <div className="flex flex-wrap gap-2">
                {GRAPH_EXPORT_FORMATS.map((row) => (
                  <Button
                    key={row.format}
                    type="button"
                    variant={exportFormat === row.format ? "default" : "outline"}
                    className="min-w-[4.5rem] flex-1 uppercase text-xs"
                    onClick={() => setExportFormat(row.format)}
                  >
                    <PublicIcon name="file-01" size={14} />
                    {row.format}
                  </Button>
                ))}
              </div>
            </div>

            <div className="flex-1 rounded-[var(--ws-radius-sm)] border border-border bg-muted/40 p-3.5 px-4">
              <div className="mb-1.5 text-xs font-bold text-muted-foreground">{ie.included_title}</div>
              <div className={cn(wsBody, "text-xs")}>{ie[exportMeta.includedKey]}</div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="w-full"
              data-testid="graph-export-audit-pack"
              onClick={() => void handleAuditPack()}
              disabled={isAuditPackBusy || isExporting}
            >
              {isAuditPackBusy ? (
                <>
                  <PublicIcon name="loader-01" size={15} className="animate-spin" />
                  {ie.preparing}
                </>
              ) : (
                <>
                  <PublicIcon name="file-01" size={15} />
                  {ie.audit_pack_button}
                </>
              )}
            </Button>

            <Button
              type="button"
              variant="secondary"
              className="w-full"
              onClick={handleExport}
              disabled={isExporting || isAuditPackBusy}
            >
              {isExporting ? (
                <>
                  <PublicIcon name="loader-01" size={15} className="animate-spin" />
                  {ie.preparing}
                </>
              ) : (
                <>
                  <PublicIcon name="download-01" size={15} />
                  {ie.export_button}
                </>
              )}
            </Button>
          </div>
        </div>
      </div>

      <div className={exWsToastStack}>
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(exWsToast, toast.type === "success" ? exWsToastSuccess : exWsToastError)}
          >
            {toast.type === "success" ? (
              <PublicIcon name="check-circle" size={16} className="shrink-0 text-ok" />
            ) : (
              <PublicIcon name="alert-circle" size={16} className="shrink-0 text-destructive" />
            )}
            <span>{toast.text}</span>
            {toast.action ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="ml-1 h-7"
                onClick={() => {
                  toast.action?.onClick();
                  setToasts((p) => p.filter((item) => item.id !== toast.id));
                }}
              >
                {toast.action.label}
              </Button>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}
