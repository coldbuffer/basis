import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { EntityRefLine } from '@/components/app/shared/workspace/entity-ref-line.js';
import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber, pickCountForm } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import {
  ledgerChunkOriginLabel,
  ledgerStatementStatusLabel,
} from '@/modules/workspace/library/lib/ledger-labels.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';

type ChunkFields = {
  heading?: string | null;
  char_start?: number | null;
  char_end?: number | null;
  token_count?: number | null;
  language?: string | null;
  origin?: string | null;
};

type ChunkSummary = ChunkFields & { id: string; ordinal: number; text: string };

type ChunkDetail = ChunkFields & {
  chunk_id: string;
  document_id: string;
  document_title: string;
  ordinal: number;
  text: string;
};

type ChunkStatement = {
  statement_id: string;
  surface_phrase: string;
  subject_id: string;
  object_entity_id: string | null;
  object_value: string | null;
  status: string;
  quote: string | null;
};

export function LedgerEvidenceInspector({ workspaceId }: { workspaceId: string }) {
  const { t, locale } = useI18n();
  const ledger = t.entities.ledger;
  const ev = ledger.evidence;
  const apiError = useApiErrorMessage();
  const [searchParams, setSearchParams] = useSearchParams();
  const docRef = searchParams.get('doc')?.trim() || null;
  const chunkId = searchParams.get('chunk')?.trim() || null;

  const [docTitle, setDocTitle] = useState<string | null>(null);
  const [docChunks, setDocChunks] = useState<ChunkSummary[]>([]);
  const [chunk, setChunk] = useState<ChunkDetail | null>(null);
  const [statements, setStatements] = useState<ChunkStatement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const labelIds = useMemo(() => {
    const ids: string[] = [];
    for (const row of statements) {
      ids.push(row.subject_id);
      if (row.object_entity_id) ids.push(row.object_entity_id);
    }
    return ids;
  }, [statements]);
  const labels = useWorkspaceNodeLabels(workspaceId, labelIds);

  useEffect(() => {
    if (!docRef || chunkId) {
      setDocChunks([]);
      setDocTitle(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void workspaceOpenApiGET<{ document: { title?: string; doc_id?: string } }>(
      workspaceId,
      `ledger/documents/${encodeURIComponent(docRef)}`,
    )
      .then((meta) => {
        if (!cancelled) {
          setDocTitle(meta.document?.title ?? meta.document?.doc_id ?? docRef);
        }
      })
      .catch(() => {
        if (!cancelled) setDocTitle(docRef);
      });
    void workspaceOpenApiGET<{ chunks: ChunkSummary[] }>(
      workspaceId,
      `ledger/documents/${encodeURIComponent(docRef)}/chunks`,
    )
      .then((data) => {
        if (!cancelled) setDocChunks(data.chunks ?? []);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(apiError(err));
          setDocChunks([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, docRef, chunkId, apiError]);

  useEffect(() => {
    if (!chunkId) {
      setChunk(null);
      setStatements([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void workspaceOpenApiGET<{ chunk: ChunkDetail; statements: ChunkStatement[] }>(
      workspaceId,
      `ledger/chunks/${encodeURIComponent(chunkId)}`,
    )
      .then((data) => {
        if (!cancelled) {
          setChunk(data.chunk);
          setStatements(data.statements ?? []);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(apiError(err));
          setChunk(null);
          setStatements([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, chunkId, apiError]);

  function clearEvidenceParams() {
    const next = new URLSearchParams(searchParams);
    next.delete('doc');
    next.delete('chunk');
    setSearchParams(next, { replace: true });
  }

  function openChunk(id: string) {
    const next = new URLSearchParams(searchParams);
    next.set('chunk', id);
    setSearchParams(next, { replace: true });
  }

  function backToChunks() {
    const next = new URLSearchParams(searchParams);
    next.delete('chunk');
    setSearchParams(next, { replace: true });
  }

  const graphFocusId =
    statements.find((row) => row.subject_id)?.subject_id ??
    statements.find((row) => row.object_entity_id)?.object_entity_id ??
    null;

  const loadingLabel = t.core.common.loading;
  const title = chunkId ? ev.chunk_title : (docTitle ?? docRef ?? '');

  function chunkMeta(row: ChunkFields): string | null {
    const loc = locale as Locale;
    const parts: string[] = [];
    if (row.heading) parts.push(row.heading);
    if (row.char_start != null && row.char_end != null) {
      parts.push(
        fmt(ev.char_range, {
          start: formatLocaleNumber(loc, row.char_start),
          end: formatLocaleNumber(loc, row.char_end),
        }),
      );
    }
    if (row.token_count != null) {
      parts.push(
        fmt(ev.token_count, { count: formatLocaleNumber(loc, row.token_count) }),
      );
    }
    if (row.language) parts.push(row.language);
    if (row.origin && (row.origin !== 'stated' || parts.length > 0)) {
      parts.push(ledgerChunkOriginLabel(ledger, row.origin));
    }
    return parts.length ? parts.join(' · ') : null;
  }

  const chunkCountLabel = fmt(
    pickCountForm(locale, docChunks.length, ev.chunk_count_one, ev.chunk_count),
    { count: formatLocaleNumber(locale as Locale, docChunks.length) },
  );

  return (
    <Dialog open={Boolean(docRef || chunkId)} onOpenChange={(open) => { if (!open) clearEvidenceParams(); }}>
      <DialogContent className="flex max-h-[min(80vh,720px)] flex-col gap-3 sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {chunkId
              ? chunk
                ? fmt(ev.chunk_doc_line, {
                    title: chunk.document_title || chunk.document_id,
                    ordinal: formatLocaleNumber(locale as Locale, chunk.ordinal),
                  })
                : loadingLabel
              : loading
                ? loadingLabel
                : chunkCountLabel}
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-3 overflow-auto text-sm">
        {error ? <p className="text-destructive">{error}</p> : null}
        {loading && !chunk && docChunks.length === 0 ? (
          <p className="text-muted-foreground">{loadingLabel}</p>
        ) : null}

        {docRef && !chunkId ? (
          <ul className="space-y-2">
            {docChunks.length === 0 && !loading ? (
              <li className="text-muted-foreground">{ev.no_chunks}</li>
            ) : (
              docChunks.map((row) => {
                const meta = chunkMeta(row);
                return (
                <li key={row.id}>
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-auto w-full flex-col items-start rounded-md border border-border px-3 py-2 text-left font-normal hover:bg-[color-mix(in_oklch,var(--primary)_7%,var(--card))]"
                    onClick={() => openChunk(row.id)}
                  >
                    <span className="font-mono text-[11px] text-muted-foreground">
                      #{formatLocaleNumber(locale as Locale, row.ordinal)}
                      {meta ? ` · ${meta}` : ''}
                    </span>
                    <p className="mt-1 line-clamp-4 whitespace-pre-wrap text-[13px] leading-snug">{row.text}</p>
                  </Button>
                </li>
                );
              })
            )}
          </ul>
        ) : null}

        {chunk ? (
          <>
            {docRef ? (
              <Button type="button" variant="outline" size="sm" className="h-8" onClick={backToChunks}>
                {ev.all_chunks}
              </Button>
            ) : null}
            {chunkMeta(chunk) ? (
              <p className="font-mono text-[11px] text-muted-foreground">{chunkMeta(chunk)}</p>
            ) : null}
            <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">
              {chunk.text}
            </pre>
            <div>
              <div className="mb-2 font-medium">{ev.statements_title}</div>
              {statements.length === 0 ? (
                <p className="text-muted-foreground">{ev.no_statements}</p>
              ) : (
                <ul className="space-y-2 text-xs">
                  {statements.map((row) => (
                    <li key={row.statement_id} className="rounded border p-2">
                      <EntityRefLine id={row.subject_id} labels={labels} />
                      <div className="mt-1">
                        <span className="font-medium">{row.surface_phrase}</span>
                        {' → '}
                        {row.object_entity_id ? (
                          <EntityRefLine id={row.object_entity_id} labels={labels} className="inline" />
                        ) : (
                          <span className="text-muted-foreground">{row.object_value}</span>
                        )}
                        <span className="ml-2 text-muted-foreground">
                          ({ledgerStatementStatusLabel(ledger, row.status)})
                        </span>
                      </div>
                      {row.quote ? (
                        <blockquote className="mt-1 border-l-2 pl-2 text-muted-foreground">
                          {row.quote}
                        </blockquote>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {graphFocusId ? (
              <Button variant="link" size="sm" className="h-auto p-0" asChild>
                <Link to={`${workspacePath(workspaceId, 'graph')}?focus=${encodeURIComponent(graphFocusId)}`}>
                  {ev.focus_in_graph}
                </Link>
              </Button>
            ) : null}
          </>
        ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
