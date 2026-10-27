/**
 * Sources library UI (upload, document table). Processing jobs live at `/workspaces/:id/processing`.
 * Mounted on route `/workspaces/:id/sources`.
 */
import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  DataPanel,
  DataPanelBody,
  DataPanelTableFooter,
  DataPanelToolbar,
  EmptyState,
  ToolbarSearch,
} from '@/components/app/shared/console/index.js';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Button } from '@/components/ui/button.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
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
import { Switch } from '@/components/ui/switch.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { Textarea } from '@/components/ui/textarea.js';
import { cn } from '@/lib/utils.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { useI18n } from '@/i18n/context.js';
import {
  compareLocaleStrings,
  fmt,
  formatLocaleDateTime,
  formatLocaleNumber,
  pickCountForm,
} from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import type { LocaleMessages } from '@/i18n/en.js';
import { messageForApiErrorCode } from '@/lib/errors/api-error-message.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { useWorkspaceWsClient } from '@/lib/workspace/ws-context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import {
  processingJobPath,
  processingPath,
  parseProcessingUrlState,
} from '@/modules/processing/lib/processing-url-state.js';
import { ProcessingOptionsSnapshot } from '@/components/app/shared/workspace/processing-options-snapshot.js';
import { type ProcessingJob, jobIsActive, statusIsProcessing } from '@/modules/processing/lib/processing-job.js';
import { parseSourcesUrlState } from '@/modules/library/lib/sources-url-state.js';
import { formatByteSize } from '@/modules/library/lib/format-byte-size.js';
import { DocumentTimelinePanel } from '../components/document-timeline-panel.js';
import { uploadExceedsMaxBytes } from '@/modules/library/lib/ingest-upload-limit.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { processingStartIdempotencyKey } from '@/modules/processing/lib/processing-idempotency.js';
import { ExtractLlmModelSelect } from '@/modules/library/components/extract-llm-model-select.js';

const PAGE_SIZE = 10;

type DocRow = {
  doc_id: string;
  filename?: string | null;
  document_id?: string;
  preview: string;
  char_count: number;
  version_status?: string | null;
  version_id?: string | null;
  version_no?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

function versionStatusLabel(
  status: string | null | undefined,
  labels: LocaleMessages['library']['sources']['version_status'],
  emptyCell: string,
): string {
  if (!status) return emptyCell;
  const key = status as keyof typeof labels;
  return key in labels ? labels[key] : status;
}

function docReadyForGraph(doc: DocRow, job?: ProcessingJob): boolean {
  if (doc.version_status === 'ready') return true;
  return job?.status === 'succeeded';
}

function docIdFromUrl(rawUrl: string): string {
  try {
    const parsed = new URL(rawUrl);
    const seg = parsed.pathname.split('/').filter(Boolean).pop() || parsed.hostname;
    const stem = seg
      .replace(/\.[^.]+$/, '')
      .replace(/[^a-zA-Z0-9._-]+/g, '-')
      .replace(/^[-._]+|[-._]+$/g, '');
    if (stem) return stem;
  } catch {
    // fallback below
  }
  return `url-${Date.now()}`;
}

const DEFAULT_CHUNK_SIZE = 1800;
const DEFAULT_CHUNK_OVERLAP = 250;
const DEFAULT_CHUNK_METHOD = 'recursive';

type ProductChunkMethod =
  | 'recursive'
  | 'sentence'
  | 'paragraph'
  | 'structural'
  | 'entity_aware';

function chunkMethodForName(name: string | null | undefined): ProductChunkMethod {
  const lower = (name ?? '').trim().toLowerCase();
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) return 'structural';
  return DEFAULT_CHUNK_METHOD;
}

function chunkSizeValid(size: number): boolean {
  return Number.isFinite(size) && size >= 200 && size <= 100_000;
}

function chunkOptionsValid(
  method: ProductChunkMethod,
  size: number,
  overlap: number,
): boolean {
  if (!chunkSizeValid(size)) return false;
  if (method !== 'recursive') return true;
  return (
    Number.isFinite(overlap) &&
    overlap >= 0 &&
    overlap <= 10_000 &&
    overlap < size
  );
}

const EXTRACT_LLM_METHOD = 'llm';

function chunkMethodChoices(
  copy: LocaleMessages['library']['sources'],
): { value: ProductChunkMethod; label: string }[] {
  return [
    { value: 'recursive', label: copy.chunk_method_recursive },
    { value: 'sentence', label: copy.chunk_method_sentence },
    { value: 'paragraph', label: copy.chunk_method_paragraph },
    { value: 'structural', label: copy.chunk_method_structural },
    { value: 'entity_aware', label: copy.chunk_method_entity_aware },
  ];
}

function ProcessSection({
  id,
  title,
  hint,
  checked,
  onCheckedChange,
  children,
}: {
  id: string;
  title: string;
  hint: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  children: ReactNode;
}) {
  return (
    <section className="rounded-md border border-border">
      <div className="flex items-start justify-between gap-3 px-3 py-3">
        <div className="min-w-0 space-y-0.5">
          <Label htmlFor={id} className="text-sm font-medium">
            {title}
          </Label>
          <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>
        </div>
        <Switch id={id} checked={checked} onCheckedChange={onCheckedChange} className="mt-0.5" />
      </div>
      <div
        className={cn(
          'space-y-3 border-t border-border px-3 py-3',
          !checked && 'pointer-events-none opacity-40',
        )}
      >
        {children}
      </div>
    </section>
  );
}

export function SourcesPage() {
  const { isAdmin } = useBasisSession();
  const { id } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = useWorkspaceWsClient();
  const { t, locale } = useI18n();
  const emptyCell = t.core.common.emptyCell;
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps } = useWorkspaceCapabilities();
  const fileRef = useRef<HTMLInputElement>(null);
  const updateFileRef = useRef<HTMLInputElement>(null);
  const jobStatusRef = useRef<Record<string, string>>({});

  const [documents, setDocuments] = useState<DocRow[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const [addOpen, setAddOpen] = useState(false);
  const sourcesUrl = parseSourcesUrlState(searchParams.toString());
  const processingUrl = parseProcessingUrlState(searchParams.toString());
  const jobFocusId = processingUrl.jobId;
  const [updateTarget, setUpdateTarget] = useState<{
    document_id: string;
    doc_id: string;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{
    document_id: string;
    doc_id: string;
  } | null>(null);
  const [deletingDocument, setDeletingDocument] = useState(false);

  const [docId, setDocId] = useState('');
  const [docText, setDocText] = useState('');
  const [docUrl, setDocUrl] = useState('');
  const [updateText, setUpdateText] = useState('');
  const [uploading, setUploading] = useState(false);
  const [processImmediately, setProcessImmediately] = useState(false);
  const [busyVersionId, setBusyVersionId] = useState<string | null>(null);
  const [configVersionId, setConfigVersionId] = useState('');
  const [chunk, setChunk] = useState(true);
  const [chunkMethod, setChunkMethod] = useState<ProductChunkMethod>(DEFAULT_CHUNK_METHOD);
  const [chunkSize, setChunkSize] = useState(1800);
  const [chunkOverlap, setChunkOverlap] = useState(250);
  const [extract, setExtract] = useState(true);
  const [extractLlmEndpointId, setExtractLlmEndpointId] = useState('');
  const [extractLlmModel, setExtractLlmModel] = useState('');
  const processDialogOptions = useMemo(
    () => ({
      chunk,
      chunk_method: chunkMethod,
      chunk_size: chunkSize,
      chunk_overlap: chunkOverlap,
      extract,
      ner_method: EXTRACT_LLM_METHOD,
      relation_method: EXTRACT_LLM_METHOD,
      extract_relations: true,
      ...(extract && extractLlmEndpointId.trim()
        ? { llm_endpoint_id: extractLlmEndpointId.trim() }
        : {}),
      ...(extract && extractLlmModel.trim() ? { llm_model: extractLlmModel.trim() } : {}),
    }),
    [chunk, chunkMethod, chunkSize, chunkOverlap, extract, extractLlmEndpointId, extractLlmModel],
  );


  const k = t.library.sources;
  const pProcessing = t.processing.jobs;
  const uploadLimitsHint = useMemo(() => {
    const upload = caps?.upload_max_bytes;
    if (!upload) return null;
    const extract = caps?.ingest_max_extract_chars;
    if (extract) {
      return fmt(k.upload_limits_hint, {
        upload: formatByteSize(upload),
        extract: formatLocaleNumber(locale as Locale, extract),
      });
    }
    return fmt(k.upload_limits_hint_upload_only, { upload: formatByteSize(upload) });
  }, [
    caps?.ingest_max_extract_chars,
    caps?.upload_max_bytes,
    k.upload_limits_hint,
    k.upload_limits_hint_upload_only,
    locale,
  ]);
  const apiErrorMessage = useCallback(
    (err: unknown) => formatUserFacingApiError(err, locale as Locale),
    [locale],
  );
  const canEdit = caps?.graph_write !== false;
  const graphEnabled = caps?.graph === true;
  const kbName = id ? getWorkspace(id)?.name : undefined;

  const graphFocusPath = useCallback(
    (docId: string) =>
      id ? `${workspacePath(id, 'graph')}?focus=${encodeURIComponent(docId)}` : '#',
    [id],
  );

  const latestJobByVersion = useMemo(() => {
    const result: Record<string, ProcessingJob> = {};
    for (const job of jobs) {
      if (!result[job.version_id]) result[job.version_id] = job;
    }
    return result;
  }, [jobs]);

  const activeJobCount = useMemo(
    () => jobs.filter((job) => jobIsActive(job.status)).length,
    [jobs],
  );
  const failedJobCount = useMemo(
    () => jobs.filter((job) => job.status === 'failed').length,
    [jobs],
  );

  const filteredDocuments = useMemo(() => {
    const q = search.trim().toLowerCase();
    const matched = !q
      ? documents
      : documents.filter(
          (doc) =>
            doc.doc_id.toLowerCase().includes(q) ||
            (doc.filename ?? '').toLowerCase().includes(q) ||
            (doc.document_id ?? '').toLowerCase().includes(q),
        );
    return [...matched].sort((a, b) =>
      compareLocaleStrings(locale as Locale, b.created_at ?? '', a.created_at ?? ''),
    );
  }, [documents, locale, search]);

  const totalPages = Math.max(1, Math.ceil(filteredDocuments.length / PAGE_SIZE));

  const pageDocuments = useMemo(() => {
    const safePage = Math.min(page, totalPages);
    const start = (safePage - 1) * PAGE_SIZE;
    return filteredDocuments.slice(start, start + PAGE_SIZE);
  }, [filteredDocuments, page, totalPages]);

  useEffect(() => {
    setPage(1);
  }, [search]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const refresh = useCallback(async () => {
    if (!id) return;
    const [docs, taskData] = await Promise.all([
      client.documents.list(),
      client.processing.list(),
    ]);
    setDocuments(docs.documents as DocRow[]);
    setJobs(taskData.jobs as ProcessingJob[]);
    window.dispatchEvent(new CustomEvent('workspace-processing-changed'));
  }, [id, client]);

  useEffect(() => {
    setLoading(true);
    void refresh()
      .catch((err) => toast.error(apiErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [apiErrorMessage, refresh]);

  useEffect(() => {
    if (!jobs.some((job) => jobIsActive(job.status))) return;
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => window.clearInterval(timer);
  }, [jobs, refresh]);

  useEffect(() => {
    if (!id || !graphEnabled) return;
    for (const job of jobs) {
      const prev = jobStatusRef.current[job.id];
      jobStatusRef.current[job.id] = job.status;
      if (prev && prev !== 'succeeded' && job.status === 'succeeded' && job.doc_id) {
        const path = graphFocusPath(job.doc_id);
        toast.success(k.toast_processing_complete, {
          description: job.document_title || job.doc_id,
          action: {
            label: k.toast_view_in_graph,
            onClick: () => navigate(path),
          },
        });
      }
    }
  }, [graphFocusPath, graphEnabled, id, jobs, navigate, k]);

  useEffect(() => {
    if (sourcesUrl.openProcessDialog && sourcesUrl.versionId) {
      setConfigVersionId(sourcesUrl.versionId);
    }
  }, [sourcesUrl.openProcessDialog, sourcesUrl.versionId]);

  const focusDocId = sourcesUrl.docId;
  const focusedDocument = useMemo(
    () => (focusDocId ? documents.find((doc) => doc.doc_id === focusDocId) : undefined),
    [documents, focusDocId],
  );

  useEffect(() => {
    if (!focusDocId || filteredDocuments.length === 0) return;
    const index = filteredDocuments.findIndex((doc) => doc.doc_id === focusDocId);
    if (index < 0) return;
    const targetPage = Math.floor(index / PAGE_SIZE) + 1;
    setPage((prev) => (prev === targetPage ? prev : targetPage));
  }, [filteredDocuments, focusDocId]);

  useEffect(() => {
    if (!focusDocId) return;
    const frame = window.requestAnimationFrame(() => {
      document.getElementById(`sources-doc-row-${focusDocId}`)?.scrollIntoView({
        block: 'nearest',
        behavior: 'smooth',
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [focusDocId, page, pageDocuments]);

  function resetAddForm() {
    setDocId('');
    setDocText('');
    setDocUrl('');
    if (fileRef.current) fileRef.current.value = '';
  }

  function closeUpdate() {
    setUpdateTarget(null);
    setUpdateText('');
    if (updateFileRef.current) updateFileRef.current.value = '';
  }

  function openAdd() {
    resetAddForm();
    setAddOpen(true);
  }

  async function afterStore(
    created: { version_id: string; unchanged?: boolean },
    close: () => void,
  ) {
    if (created.unchanged) {
      toast.info(k.toast_unchanged);
      return;
    }
    if (processImmediately) {
      await client.processing.start({
        version_id: created.version_id,
        wait: false,
        idempotency_key: processingStartIdempotencyKey(created.version_id),
      });
      toast.success(k.toast_saved_queued);
    } else {
      toast.success(k.toast_saved);
    }
    close();
    await refresh();
  }

  async function saveText(event: FormEvent) {
    event.preventDefault();
    if (!id) return;
    setUploading(true);
    try {
      const created = await client.documents.ingestText({
        doc_id: docId.trim() || `text-${Date.now()}`,
        text: docText,
      });
      await afterStore(created, () => {
        resetAddForm();
        setAddOpen(false);
      });
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function saveUrl(event: FormEvent) {
    event.preventDefault();
    if (!id) return;
    const trimmedUrl = docUrl.trim();
    if (!trimmedUrl.startsWith('http://') && !trimmedUrl.startsWith('https://')) {
      toast.error(k.invalid_url);
      return;
    }
    setUploading(true);
    try {
      const created = await client.documents.ingestUrl({
        doc_id: docId.trim() || docIdFromUrl(trimmedUrl),
        url: trimmedUrl,
      });
      await afterStore(created, () => {
        resetAddForm();
        setAddOpen(false);
      });
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  function rejectOversizedUpload(file: File): boolean {
    const max = caps?.upload_max_bytes;
    if (!uploadExceedsMaxBytes(file, max)) return false;
    toast.error(
      fmt(k.file_too_large, { upload: formatByteSize(max ?? file.size) }),
    );
    return true;
  }

  async function uploadFile(event: FormEvent) {
    event.preventDefault();
    if (!id || !fileRef.current?.files?.[0]) return;
    if (rejectOversizedUpload(fileRef.current.files[0])) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', fileRef.current.files[0]);
      if (docId.trim()) form.append('doc_id', docId.trim());
      const data = await client.documents.upload(form);
      await afterStore(data, () => {
        resetAddForm();
        setAddOpen(false);
      });
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function saveUpdateText(event: FormEvent) {
    event.preventDefault();
    if (!updateTarget?.document_id || !updateText.trim()) return;
    setUploading(true);
    try {
      const created = await client.documents.appendTextVersion(updateTarget.document_id, {
        text: updateText,
      });
      await afterStore(created, () => {
        setUpdateText('');
        closeUpdate();
      });
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function uploadUpdateFile(event: FormEvent) {
    event.preventDefault();
    if (!updateTarget?.document_id || !updateFileRef.current?.files?.[0]) return;
    if (rejectOversizedUpload(updateFileRef.current.files[0])) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', updateFileRef.current.files[0]);
      const data = await client.documents.uploadVersion(updateTarget.document_id, form);
      await afterStore(data, () => closeUpdate());
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setUploading(false);
    }
  }

  async function startConfigured(event: FormEvent) {
    event.preventDefault();
    if (!configVersionId || (!chunk && !extract)) return;
    if (chunk && !chunkOptionsValid(chunkMethod, chunkSize, chunkOverlap)) return;
    setBusyVersionId(configVersionId);
    try {
      await client.processing.start({
        version_id: configVersionId,
        wait: false,
        ...processDialogOptions,
        idempotency_key: processingStartIdempotencyKey(configVersionId, processDialogOptions),
      });
      closeConfig();
      toast.success(k.toast_queued_custom);
      await refresh();
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusyVersionId(null);
    }
  }

  async function retry(job: ProcessingJob) {
    setBusyVersionId(job.version_id);
    try {
      await client.processing.retry(job.id);
      toast.success(k.toast_retry_queued);
      await refresh();
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusyVersionId(null);
    }
  }

  async function confirmDeleteDocument() {
    if (!deleteTarget?.document_id) return;
    setDeletingDocument(true);
    try {
      await client.documents.delete(deleteTarget.document_id);
      toast.success(k.toast_document_deleted);
      setDeleteTarget(null);
      await refresh();
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setDeletingDocument(false);
    }
  }

  function openConfig(versionId: string) {
    const doc = documents.find((item) => item.version_id === versionId);
    setChunk(true);
    setChunkMethod(chunkMethodForName(doc?.filename || doc?.doc_id));
    setChunkSize(DEFAULT_CHUNK_SIZE);
    setChunkOverlap(DEFAULT_CHUNK_OVERLAP);
    setExtract(true);
    setConfigVersionId(versionId);
    const next = new URLSearchParams(searchParams);
    next.set('version', versionId);
    next.set('process', '1');
    setSearchParams(next, { replace: true });
  }

  function closeConfig() {
    setConfigVersionId('');
    const next = new URLSearchParams(searchParams);
    next.delete('version');
    next.delete('process');
    setSearchParams(next, { replace: true });
  }

  const openDocument = useCallback(
    (docId: string) => {
      const next = new URLSearchParams(searchParams);
      next.set('doc', docId);
      next.delete('chunk');
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  function openUpdate(doc: DocRow) {
    if (!doc.document_id) return;
    setUpdateText('');
    if (updateFileRef.current) updateFileRef.current.value = '';
    setUpdateTarget({ document_id: doc.document_id, doc_id: doc.doc_id });
  }

  const columns: DataTableColumn<DocRow>[] = useMemo(() => {
    const documentCol = 'doc_id';
    const filenameCol = k.col_filename;
    const statusCol = k.col_status;
    const charsCol = k.col_chars;
    const createdCol = k.col_created_at;
    const updatedCol = k.col_updated_at;
    const actionsCol = k.col_actions;

    return [
      {
        key: 'doc',
        header: documentCol,
        render: (doc) => (
          <div className="min-w-0">
            {id ? (
              <Button
                type="button"
                variant="link"
                className="h-auto max-w-full justify-start truncate p-0 font-medium"
                onClick={() => openDocument(doc.doc_id)}
              >
                {doc.doc_id}
              </Button>
            ) : (
              <span className="font-medium">{doc.doc_id}</span>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
              {doc.version_no != null ? (
                <span>
                  {fmt(k.table_version_no, {
                    version: formatLocaleNumber(locale as Locale, doc.version_no),
                  })}
                </span>
              ) : null}
              {doc.version_id ? (() => {
                const rowJob = latestJobByVersion[doc.version_id];
                if (!rowJob) return null;
                return (
                  <span className="block max-w-md space-y-0.5">
                    <span>
                      {fmt(k.history_attempt, {
                        attempt: formatLocaleNumber(locale as Locale, rowJob.attempt),
                      })}
                    </span>
                    {rowJob.error_code ? (
                      <span
                        className="block text-destructive"
                        data-testid={`sources-job-error-${rowJob.id}`}
                      >
                        <span>
                          {messageForApiErrorCode(rowJob.error_code, locale) ??
                            rowJob.error_code}
                          <span className="ml-1 font-mono text-[10px] opacity-80">
                            ({rowJob.error_code})
                          </span>
                        </span>
                        {rowJob.error_detail?.message ? (
                          <span className="block text-muted-foreground">
                            {rowJob.error_detail.message}
                          </span>
                        ) : null}
                      </span>
                    ) : null}
                  </span>
                );
              })() : null}
            </div>
          </div>
        ),
      },
      {
        key: 'filename',
        header: filenameCol,
        render: (doc) => (
          <span className="text-muted-foreground">{doc.filename || emptyCell}</span>
        ),
      },
      {
        key: 'status',
        header: statusCol,
        width: '8.5rem',
        render: (doc) => {
          const job = doc.version_id ? latestJobByVersion[doc.version_id] : undefined;
          const status =
            job?.status === 'running'
              ? job.version_status
              : job?.status === 'queued'
                ? 'queued'
                : doc.version_status ?? job?.status;
          const statusBody = (
            <>
              {status === 'ready' ? (
                <span className="size-1.5 shrink-0 rounded-full bg-ok" aria-hidden />
              ) : statusIsProcessing(status) ? (
                <Spinner className="size-3" />
              ) : null}
              <span className={status === 'failed' ? 'text-destructive' : undefined}>
                {versionStatusLabel(status, k.version_status, emptyCell)}
              </span>
            </>
          );
          if (job && id) {
            return (
              <Link
                to={processingJobPath(id, job.id)}
                className="inline-flex items-center gap-1.5 text-xs underline-offset-2 hover:underline"
                data-testid={`sources-job-status-${job.id}`}
              >
                {statusBody}
              </Link>
            );
          }
          return <span className="inline-flex items-center gap-1.5 text-xs">{statusBody}</span>;
        },
      },
      {
        key: 'chars',
        header: charsCol,
        width: '5rem',
        hideBelow: 'md',
        render: (doc) => formatLocaleNumber(locale as Locale, doc.char_count),
      },
      {
        key: 'created_at',
        header: createdCol,
        width: '11rem',
        render: (doc) => (
          <span className="whitespace-nowrap text-muted-foreground">
            {doc.created_at ? formatLocaleDateTime(locale as Locale, doc.created_at) : emptyCell}
          </span>
        ),
      },
      {
        key: 'updated_at',
        header: updatedCol,
        width: '11rem',
        render: (doc) => (
          <span className="whitespace-nowrap text-muted-foreground">
            {doc.updated_at ? formatLocaleDateTime(locale as Locale, doc.updated_at) : emptyCell}
          </span>
        ),
      },
      {
        key: 'actions',
        header: actionsCol,
        align: 'right',
        render: (doc) => {
          const job = doc.version_id ? latestJobByVersion[doc.version_id] : undefined;
          const busy = busyVersionId === doc.version_id;
          const canProcess =
            canEdit && doc.version_id && doc.version_status === 'uploaded';
          const canRetry = canEdit && job?.status === 'failed';
          const canUpdate = canEdit && doc.document_id;
          const canDelete = canEdit && doc.document_id;
          const rowJob = doc.version_id ? latestJobByVersion[doc.version_id] : undefined;
          const canGraph =
            graphEnabled && docReadyForGraph(doc, rowJob);

          if (!canProcess && !canRetry && !canUpdate && !canGraph && !canDelete) {
            return <span className="text-muted-foreground">{emptyCell}</span>;
          }

          const actionClass = 'h-7 px-2 text-xs';
          return (
            <div className="flex flex-wrap justify-end gap-1.5">
              {canProcess ? (
                <Button
                  type="button"
                  size="sm"
                  className={actionClass}
                  disabled={busy}
                  onClick={() => openConfig(doc.version_id!)}
                >
                  {k.action_chunk_extract}
                </Button>
              ) : null}
              {canRetry ? (
                <Button
                  type="button"
                  size="sm"
                  className={actionClass}
                  disabled={busy}
                  onClick={() => void retry(job!)}
                >
                  {k.action_retry}
                </Button>
              ) : null}
              {canUpdate ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className={actionClass}
                  onClick={() => openUpdate(doc)}
                >
                  {k.action_update}
                </Button>
              ) : null}
              {canGraph && id ? (
                <Button type="button" size="sm" variant="outline" className={actionClass} asChild>
                  <Link to={graphFocusPath(doc.doc_id)}>{k.action_graph}</Link>
                </Button>
              ) : null}
              {canDelete ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className={`${actionClass} text-destructive`}
                  onClick={() =>
                    setDeleteTarget({
                      document_id: doc.document_id!,
                      doc_id: doc.doc_id,
                    })
                  }
                >
                  {k.action_delete}
                </Button>
              ) : null}
            </div>
          );
        },
      },
    ];
  }, [
    k,
    id,
    canEdit,
    busyVersionId,
    latestJobByVersion,
    openConfig,
    retry,
    openUpdate,
    graphEnabled,
    graphFocusPath,
    latestJobByVersion,
    setDeleteTarget,
    openDocument,
    locale,
    emptyCell,
  ]);

  const configDoc = documents.find((doc) => doc.version_id === configVersionId);
  const chunkMethods = chunkMethodChoices(k);
  const chunkOverlapEnabled = chunkMethod === 'recursive';
  const chunkReady = !chunk || chunkOptionsValid(chunkMethod, chunkSize, chunkOverlap);
  const canStartProcessing =
    Boolean(configVersionId) &&
    (chunk || extract) &&
    chunkReady &&
    busyVersionId !== configVersionId &&
    (!extract ||
      (Boolean(extractLlmEndpointId.trim()) && Boolean(extractLlmModel.trim())));

  const documentCountLabel = fmt(
    pickCountForm(locale, filteredDocuments.length, k.document_count_one, k.document_count),
    { count: formatLocaleNumber(locale, filteredDocuments.length) },
  );

  if (id && jobFocusId) {
    return <Navigate to={processingJobPath(id, jobFocusId)} replace />;
  }

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: kbName ?? id ?? t.core.common.ellipsis, to: id ? workspacePath(id, 'graph') : '/workspaces' },
        { label: t.library.menu.sources },
      ]}
      subtitle={t.library.page.subtitle}
    >
      <DataPanel>
        <DataPanelToolbar
          className="flex-nowrap"
          search={
            <ToolbarSearch
              className="min-w-0 w-full max-w-md flex-1 sm:w-72 sm:flex-none"
              placeholder={k.search_placeholder}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          }
          actions={
            <>
              <Button type="button" variant="outline" size="sm" asChild>
                <Link
                  to={
                    id
                      ? processingPath(id, {
                          filter: failedJobCount > 0 ? 'failed' : undefined,
                        })
                      : '#'
                  }
                  data-testid="sources-job-history"
                  data-sources-job-nav={
                    failedJobCount > 0 ? 'failed' : 'history'
                  }
                >
                  {k.job_history}
                  {activeJobCount > 0 ? (
                    <span
                      className="ml-1.5 inline-flex min-w-[1.25rem] items-center justify-center rounded-md bg-primary/15 px-1.5 text-xs font-medium tabular-nums text-primary"
                      data-testid="sources-active-jobs-badge"
                    >
                      {formatLocaleNumber(locale as Locale, activeJobCount)}
                    </span>
                  ) : failedJobCount > 0 ? (
                    <span
                      className="ml-1.5 inline-flex min-w-[1.25rem] items-center justify-center rounded-md bg-destructive/15 px-1.5 text-xs font-medium tabular-nums text-destructive"
                      data-testid="sources-failed-jobs-badge"
                    >
                      {formatLocaleNumber(locale as Locale, failedJobCount)}
                    </span>
                  ) : null}
                </Link>
              </Button>
              {canEdit ? (
                <Button type="button" size="sm" onClick={openAdd}>
                  {k.add_document}
                </Button>
              ) : null}
            </>
          }
        />

        <DataPanelBody padded={false} className="mt-2">
          {loading && documents.length === 0 ? (
            <div className="flex justify-center py-16">
              <Spinner className="size-6" />
            </div>
          ) : filteredDocuments.length === 0 ? (
            <EmptyState
              title={k.empty_title}
              description={k.empty_description}
              action={
                canEdit ? (
                  <Button type="button" size="sm" onClick={openAdd}>
                    {k.add_document}
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <>
              <DataTable
                columns={columns}
                data={pageDocuments}
                rowKey={(doc) => doc.document_id ?? doc.doc_id}
                rowDomId={(doc) => `sources-doc-row-${doc.doc_id}`}
                rowClassName={(doc) =>
                  focusDocId && doc.doc_id === focusDocId
                    ? 'bg-muted/40 ring-2 ring-primary ring-inset'
                    : undefined
                }
                className="border-0"
              />
              <DataPanelTableFooter
                countLabel={documentCountLabel}
                page={page}
                totalPages={totalPages}
                onPageChange={setPage}
              />
              {id && focusedDocument?.document_id ? (
                <DocumentTimelinePanel
                  workspaceId={id}
                  documentRef={focusedDocument.document_id}
                  docId={focusedDocument.doc_id}
                />
              ) : null}
            </>
          )}
        </DataPanelBody>
      </DataPanel>

      <Dialog open={addOpen} onOpenChange={(open) => {
        setAddOpen(open);
        if (!open) resetAddForm();
      }}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{k.add_document}</DialogTitle>
            <DialogDescription>{k.add_dialog_desc}</DialogDescription>
          </DialogHeader>
          <Tabs defaultValue="file">
            <TabsList className="w-full">
              <TabsTrigger value="file" className="flex-1">
                {k.tab_upload}
              </TabsTrigger>
              <TabsTrigger value="text" className="flex-1">
                {k.tab_paste}
              </TabsTrigger>
              <TabsTrigger value="url" className="flex-1">
                {k.tab_url}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="file">
              <form className="space-y-4 pt-2" onSubmit={uploadFile}>
                <div className="space-y-2">
                  <Label htmlFor="add-doc-id">{k.doc_id_optional}</Label>
                  <Input
                    id="add-doc-id"
                    value={docId}
                    onChange={(event) => setDocId(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="add-file">{k.label_file}</Label>
                  <Input
                    id="add-file"
                    ref={fileRef}
                    type="file"
                    accept=".txt,.md,.pdf,.docx,.html,.json,.csv"
                    required
                    data-testid="sources-add-file-input"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file && rejectOversizedUpload(file)) {
                        event.target.value = '';
                      }
                    }}
                  />
                  {uploadLimitsHint ? (
                    <p className="text-xs text-muted-foreground" data-testid="sources-upload-limits-hint">
                      {uploadLimitsHint}
                    </p>
                  ) : null}
                </div>
                <DialogFooter className="px-0">
                  <Button type="submit" disabled={uploading}>
                    {uploading ? k.uploading : k.upload}
                  </Button>
                </DialogFooter>
              </form>
            </TabsContent>
            <TabsContent value="text">
              <form className="space-y-4 pt-2" onSubmit={saveText}>
                <div className="space-y-2">
                  <Label htmlFor="add-text-doc-id">{k.doc_id_optional}</Label>
                  <Input
                    id="add-text-doc-id"
                    value={docId}
                    onChange={(event) => setDocId(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="add-text">{k.label_text}</Label>
                  <Textarea
                    id="add-text"
                    rows={6}
                    value={docText}
                    onChange={(event) => setDocText(event.target.value)}
                    required
                  />
                </div>
                <DialogFooter className="px-0">
                  <Button type="submit" disabled={uploading}>
                    {k.save}
                  </Button>
                </DialogFooter>
              </form>
            </TabsContent>
            <TabsContent value="url">
              <form className="space-y-4 pt-2" onSubmit={saveUrl}>
                <div className="space-y-2">
                  <Label htmlFor="add-url-doc-id">{k.doc_id_optional}</Label>
                  <Input
                    id="add-url-doc-id"
                    value={docId}
                    onChange={(event) => setDocId(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="add-url">{k.label_url}</Label>
                  <Input
                    id="add-url"
                    type="url"
                    placeholder={k.url_placeholder}
                    value={docUrl}
                    onChange={(event) => setDocUrl(event.target.value)}
                    required
                  />
                </div>
                <DialogFooter className="px-0">
                  <Button type="submit" disabled={uploading}>
                    {uploading ? k.fetching_url : k.fetch_url}
                  </Button>
                </DialogFooter>
              </form>
            </TabsContent>
          </Tabs>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox
              checked={processImmediately}
              onCheckedChange={(checked) => setProcessImmediately(checked === true)}
            />
            {k.process_after_save}
          </label>
        </DialogContent>
      </Dialog>

      <Dialog
        open={updateTarget !== null}
        onOpenChange={(open) => {
          if (!open) closeUpdate();
        }}
      >
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>{k.update_dialog_title}</DialogTitle>
            <DialogDescription>{updateTarget?.doc_id}</DialogDescription>
          </DialogHeader>
          <Tabs defaultValue="file">
            <TabsList className="w-full">
              <TabsTrigger value="file" className="flex-1">
                {k.tab_new_file}
              </TabsTrigger>
              <TabsTrigger value="text" className="flex-1">
                {k.tab_new_text}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="file">
              <form className="space-y-4 pt-2" onSubmit={uploadUpdateFile}>
                <Input
                  ref={updateFileRef}
                  type="file"
                  required
                  data-testid="sources-update-file-input"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file && rejectOversizedUpload(file)) {
                      event.target.value = '';
                    }
                  }}
                />
                <DialogFooter className="px-0">
                  <Button type="submit" disabled={uploading}>
                    {uploading ? k.uploading : k.upload_version}
                  </Button>
                </DialogFooter>
              </form>
            </TabsContent>
            <TabsContent value="text">
              <form className="space-y-4 pt-2" onSubmit={saveUpdateText}>
                <Textarea
                  rows={6}
                  value={updateText}
                  onChange={(event) => setUpdateText(event.target.value)}
                  required
                />
                <DialogFooter className="px-0">
                  <Button type="submit" disabled={uploading || !updateText.trim()}>
                    {k.save_version}
                  </Button>
                </DialogFooter>
              </form>
            </TabsContent>
          </Tabs>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <Checkbox
              checked={processImmediately}
              onCheckedChange={(checked) => setProcessImmediately(checked === true)}
            />
            {k.process_after_version_save}
          </label>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(configVersionId)} onOpenChange={(open) => !open && closeConfig()}>
        <DialogContent className="max-h-[min(90vh,44rem)] min-w-0 gap-4 overflow-x-hidden overflow-y-auto sm:max-w-lg">
          <DialogHeader className="min-w-0 space-y-1 pr-8">
            <DialogTitle>{k.process_dialog_title}</DialogTitle>
            {configDoc ? (
              <p className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
                <span className="min-w-0 break-all font-medium">
                  {configDoc.filename || configDoc.doc_id}
                </span>
                {configDoc.filename ? (
                  <span className="min-w-0 break-all font-mono text-xs text-muted-foreground">
                    {configDoc.doc_id}
                  </span>
                ) : null}
                {configDoc.version_no ? (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    v{configDoc.version_no}
                  </span>
                ) : null}
              </p>
            ) : null}
          </DialogHeader>
          <form className="space-y-3" onSubmit={startConfigured}>
            <div className="space-y-3">
              <ProcessSection
                id="process-chunk"
                title={k.section_chunk}
                hint={k.section_chunk_hint}
                checked={chunk}
                onCheckedChange={setChunk}
              >
                <div className="space-y-1.5">
                  <Label>{k.chunk_method}</Label>
                  <Select
                    value={chunkMethod}
                    onValueChange={(value) => setChunkMethod(value as ProductChunkMethod)}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {chunkMethods.map((item) => (
                        <SelectItem key={item.value} value={item.value}>
                          {item.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {chunkMethod === 'entity_aware' ? (
                    <p className="text-xs text-muted-foreground">{k.chunk_method_entity_aware_hint}</p>
                  ) : null}
                </div>
                <div
                  className={cn(
                    'grid gap-3',
                    chunkOverlapEnabled ? 'grid-cols-2' : 'grid-cols-1',
                  )}
                >
                  <div className="space-y-1.5">
                    <Label htmlFor="chunk-size">{k.chunk_size}</Label>
                    <Input
                      id="chunk-size"
                      type="number"
                      min={200}
                      max={100000}
                      value={chunkSize}
                      onChange={(event) => setChunkSize(Number(event.target.value))}
                    />
                  </div>
                  {chunkOverlapEnabled ? (
                    <div className="space-y-1.5">
                      <Label htmlFor="chunk-overlap">{k.chunk_overlap}</Label>
                      <Input
                        id="chunk-overlap"
                        type="number"
                        min={0}
                        max={10000}
                        value={chunkOverlap}
                        onChange={(event) => setChunkOverlap(Number(event.target.value))}
                      />
                    </div>
                  ) : null}
                </div>
                {chunk && !chunkReady ? (
                  <p className="text-xs text-destructive">
                    {chunkOverlapEnabled && chunkOverlap >= chunkSize
                      ? k.chunk_overlap_too_large
                      : k.chunk_size_range}
                  </p>
                ) : null}
              </ProcessSection>
              <ProcessSection
                id="process-extract"
                title={k.section_extract}
                hint={k.section_extract_hint}
                checked={extract}
                onCheckedChange={setExtract}
              >
                <p className="text-sm text-muted-foreground">{k.extract_llm_only}</p>
                {id ? (
                  <ExtractLlmModelSelect
                    workspaceId={id}
                    active={extract}
                    endpointId={extractLlmEndpointId}
                    onEndpointIdChange={setExtractLlmEndpointId}
                    modelId={extractLlmModel}
                    onModelIdChange={setExtractLlmModel}
                    disabled={busyVersionId === configVersionId}
                  />
                ) : null}
                <p
                  className="text-xs text-muted-foreground"
                  data-testid="sources-llm-ner-hint"
                >
                  {isAdmin ? (
                    <>
                      {k.llm_credentials_hint_prefix}{' '}
                      <Link to="/admin/models" className="text-primary hover:underline">
                        {k.llm_ner_models_link}
                      </Link>
                      {k.llm_credentials_hint_suffix}
                    </>
                  ) : (
                    k.llm_ner_hint_non_admin
                  )}
                </p>
              </ProcessSection>
              {!chunk && !extract ? (
                <p className="text-xs text-muted-foreground">
                  {k.need_chunk_or_extract}
                </p>
              ) : null}
              {chunk || extract ? (
                <ProcessingOptionsSnapshot
                  className="rounded-md border border-border/80 bg-muted/30 px-3 py-2"
                  options={processDialogOptions}
                  summaryTitle={pProcessing.process_dialog_options_preview}
                  summaryTestId="sources-process-options-preview"
                  jsonTestId="sources-process-options-json"
                  preClassName="mt-2 max-h-32 overflow-auto rounded bg-background/80 p-2 text-[10px]"
                />
              ) : null}
            </div>
            <DialogFooter className="border-t border-border pt-4">
              <Button type="button" variant="outline" onClick={closeConfig}>
                {t.core.common.cancel}
              </Button>
              <Button type="submit" disabled={!canStartProcessing}>
                {busyVersionId === configVersionId ? k.queuing : k.start_processing}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open && !deletingDocument) setDeleteTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{k.delete_title}</AlertDialogTitle>
            <AlertDialogDescription>
              {fmt(k.delete_description, { docId: deleteTarget?.doc_id ?? '' })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingDocument}>
              {t.core.common.cancel}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={deletingDocument}
              onClick={(event) => {
                event.preventDefault();
                void confirmDeleteDocument();
              }}
            >
              {deletingDocument ? k.deleting : k.delete}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConsolePageLayout>
  );
}
