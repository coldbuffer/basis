import type { Locale } from '@/i18n/locale.js';
import { requestFailedStatusMessage } from '@/i18n/format.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import type { BasisApiError } from '@/lib/openapi/transport.js';

import { errorFromApiResponse } from '@/lib/errors/api-error.js';
import { getToken } from '@/lib/auth/auth-token.js';
import { basisApiUrl } from '@/lib/session/basis-session-fetch.js';
import { basisSessionClient } from '@/lib/session/basis-session-client.js';
import { workspaceApiRoot } from '@/lib/workspace/api-path.js';
import { ensureRequestIdHeader } from '@/lib/workspace/request-id.js';

function ingestPollTimeoutMessage(locale: Locale): string {
  return messagesForLocale(locale).library.sources.ingest_poll_timeout;
}

export type ExplorerCapabilities = {
  graph_snapshot: boolean;
  graph_runtime: boolean;
};

export type DocumentStoreResult = {
  document_id: string;
  version_id: string;
  doc_id: string;
  status: string;
  version_no?: number;
  new_document?: boolean;
  new_version?: boolean;
  unchanged?: boolean;
  byte_size?: number;
};

export class WorkspaceWsClient {
  readonly workspaceId: string;
  private readonly signal?: AbortSignal;
  private readonly locale: Locale;

  constructor(workspaceId: string, signal?: AbortSignal, locale: Locale = 'en') {
    this.workspaceId = workspaceId;
    this.signal = signal;
    this.locale = locale;
  }

  /** Workspace-scoped API path; every graph call must go through here. */
  path(subpath: string): string {
    const suffix = subpath.startsWith('/') ? subpath : `/${subpath}`;
    if (!suffix.startsWith('/api/')) {
      return `${workspaceApiRoot(this.workspaceId)}${suffix}`;
    }
    return suffix;
  }

  async requestMultipart<T>(subpath: string, form: FormData): Promise<{ data: T; status: number }> {
    const headers = new Headers();
    ensureRequestIdHeader(headers);
    const token = getToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(basisApiUrl(this.path(subpath)), {
      method: 'POST',
      headers,
      body: form,
      signal: this.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw errorFromApiResponse(
        response.status,
        data,
        requestFailedStatusMessage(this.locale, response.status),
        this.locale,
      );
    }
    return { data: data as T, status: response.status };
  }

  async request<T>(subpath: string, init: RequestInit = {}): Promise<T> {
    try {
      return await basisSessionClient().fetchJson<T>(this.path(subpath), {
        ...init,
        signal: this.signal ?? init.signal,
      });
    } catch (err) {
      const apiErr = err as BasisApiError;
      if (typeof apiErr.status === 'number') {
        throw errorFromApiResponse(
          apiErr.status,
          apiErr.data,
          requestFailedStatusMessage(this.locale, apiErr.status),
          this.locale,
        );
      }
      throw err;
    }
  }

  realtimeTicket() {
    return this.request<{ ticket: string; projection_revision: number }>('realtime-ticket', {
      method: 'POST',
    });
  }

  documents = {
    list: () => this.request<{ documents: unknown[] }>('documents'),
    ingestText: (body: {
      doc_id: string;
      text: string;
    }) =>
      this.request<DocumentStoreResult>('documents', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    ingestUrl: (body: {
      doc_id: string;
      url: string;
    }) =>
      this.request<DocumentStoreResult>('documents', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    upload: async (form: FormData) => {
      const { data } = await this.requestMultipart<DocumentStoreResult>(
        'documents/upload',
        form,
      );
      return data;
    },
    appendTextVersion: (documentId: string, body: { text: string }) =>
      this.request<DocumentStoreResult>(`documents/${documentId}/versions`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    uploadVersion: async (documentId: string, form: FormData) => {
      const { data } = await this.requestMultipart<DocumentStoreResult>(
        `documents/${documentId}/versions/upload`,
        form,
      );
      return data;
    },
    delete: (documentId: string) =>
      this.request<{ ok: boolean; doc_id?: string; chunk_ids?: string[] }>(
        `documents/${encodeURIComponent(documentId)}`,
        { method: 'DELETE' },
      ),
  };

  processing = {
    listLlmProviders: () =>
      this.request<{
        providers: Array<{ id: string; provider: string; api_base: string }>;
      }>('processing/llm-providers'),
    listLlmModels: (providerId: string) =>
      this.request<{
        ok: boolean;
        error?: string;
        models?: Array<{ id: string; name: string; display_name: string }>;
      }>(`processing/llm-models?provider_id=${encodeURIComponent(providerId)}`),
    start: (body: {
      version_id: string;
      wait?: boolean;
      chunk?: boolean;
      chunk_method?: string;
      chunk_size?: number;
      chunk_overlap?: number;
      extract?: boolean;
      ner_method?: string;
      ner_model?: string;
      llm_model?: string;
      relation_method?: string;
      extract_relations?: boolean;
      idempotency_key?: string;
    }) =>
      this.request<{ job_id?: string; accepted?: boolean; ledger_status?: string }>(
        'processing/jobs',
        {
          method: 'POST',
          body: JSON.stringify(body),
        },
      ),
    list: () => this.request<{ jobs: unknown[] }>('processing/jobs'),
    retry: (jobId: string) =>
      this.request<{ job_id?: string; accepted?: boolean }>(
        `processing/jobs/${encodeURIComponent(jobId)}/retry`,
        {
          method: 'POST',
          body: JSON.stringify({ wait: false }),
        },
      ),
  };

  ingest = {
    listJobs: (params?: { status?: string; limit?: number }) => {
      const q = new URLSearchParams();
      if (params?.status) q.set('status', params.status);
      if (params?.limit) q.set('limit', String(params.limit));
      const suffix = q.toString() ? `?${q}` : '';
      return this.request<{ jobs: unknown[]; processing_jobs_path?: string }>(
        `ingest/jobs${suffix}`,
      );
    },
    getJob: (jobId: string) =>
      this.request<{
        job: { status: string; error_code?: string | null };
        version?: { status: string } | null;
      }>(`ingest/jobs/${jobId}`),
    pollJob: async (jobId: string, timeoutMs = 120_000, locale: Locale = 'en') => {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        const payload = await this.ingest.getJob(jobId);
        const status = payload.job.status;
        if (status === 'succeeded' || status === 'failed' || status === 'cancelled') {
          return payload;
        }
        await new Promise((resolve) => setTimeout(resolve, 800));
      }
      throw new Error(ingestPollTimeoutMessage(locale));
    },
  };

  graph = {
    stats: () =>
      this.request<{
        node_count: number;
        node_count_active?: number;
        node_count_archived?: number;
        edge_count: number;
      }>('graph/stats'),
    snapshot: (params?: { limit_nodes?: number; limit_edges?: number }) => {
      const q = new URLSearchParams();
      if (params?.limit_nodes) q.set('limit_nodes', String(params.limit_nodes));
      if (params?.limit_edges) q.set('limit_edges', String(params.limit_edges));
      const qs = q.toString();
      return this.request(`graph/snapshot${qs ? `?${qs}` : ''}`);
    },
    nodes: (params?: { search?: string; limit?: number; node_type?: string }) => {
      const q = new URLSearchParams();
      if (params?.search) q.set('search', params.search);
      if (params?.limit) q.set('limit', String(params.limit));
      if (params?.node_type) q.set('node_type', params.node_type);
      return this.request<{ nodes: unknown[]; total: number }>(`graph/nodes?${q}`);
    },
    neighbors: (nodeId: string, depth = 1, includeArchived = false) => {
      const q = new URLSearchParams({ depth: String(depth) });
      if (includeArchived) q.set('include_archived', 'true');
      return this.request<{ neighbors: unknown[] }>(
        `graph/nodes/${encodeURIComponent(nodeId)}/neighbors?${q}`,
      );
    },
    path: (source: string, target: string) => {
      const q = new URLSearchParams({ source, target });
      return this.request(`graph/path?${q}`);
    },
    search: (body: { query: string; limit?: number; at?: string; include_archived?: boolean }) =>
      this.request<{
        results: { node: { id: string; type: string; content: string }; score: number }[];
        temporal_filter?: boolean;
        at?: string;
      }>('graph/search', { method: 'POST', body: JSON.stringify(body) }),
    rebuild: () =>
      this.request<{
        projection_revision?: number;
        projection_status?: string;
        node_count?: number;
        edge_count?: number;
      }>('graph/rebuild', { method: 'POST' }),
  };
}

/** @internal test helper */
export function explorerPathForWorkspace(workspaceId: string, subpath: string): string {
  return new WorkspaceWsClient(workspaceId).path(subpath);
}
