/** OpenAPI v1 transport for the web app (`openapi-fetch`; regen via `npm run gen:openapi-types`). */

import createOpenApiClient from "openapi-fetch";

import type { paths } from "./schema.d.ts";

export type { paths };

export type BasisOpenApiClient = ReturnType<typeof createOpenApiClient<paths>>;

export type BasisClientOptions = {
  baseUrl: string;
  accessToken: string;
};

export type BasisSessionClientOptions = {
  /** Empty string = same-origin (Vite dev proxy). */
  baseUrl?: string;
  getAccessToken: () => string | null;
  beforeRequest?: (headers: Headers) => void;
};

export type BasisPublicOpenApiClientOptions = {
  baseUrl?: string;
  beforeRequest?: (headers: Headers) => void;
};

export type BasisApiError = Error & { status: number; data: unknown };

export function createBasisSessionClient(options: BasisSessionClientOptions) {
  const base = (options.baseUrl ?? "").replace(/\/$/, "");

  function apiUrl(path: string): string {
    const segment = path.startsWith("/") ? path : `/${path}`;
    return `${base}${segment}`;
  }

  function applySessionAuth(headers: Headers): void {
    options.beforeRequest?.(headers);
    const token = options.getAccessToken();
    if (token && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  function sessionFetch(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    applySessionAuth(headers);
    return fetch(apiUrl(path), { ...init, headers });
  }

  async function fetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    applySessionAuth(headers);
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const res = await fetch(apiUrl(path), { ...init, headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(res.statusText || "request failed") as BasisApiError;
      err.status = res.status;
      err.data = data;
      throw err;
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return data as T;
  }

  function authPath(subpath: string): string {
    const segment = subpath.replace(/^\//, "");
    return `/api/v1/auth/${segment}`;
  }

  function platformPath(subpath: string): string {
    const segment = subpath.replace(/^\//, "");
    return `/api/v1/${segment}`;
  }

  function workspacePath(workspaceId: string, subpath: string): string {
    const segment = subpath.replace(/^\//, "");
    const root = `/api/v1/workspaces/${encodeURIComponent(workspaceId)}`;
    return segment ? `${root}/${segment}` : root;
  }

  function openapiClient(): BasisOpenApiClient {
    const token = options.getAccessToken();
    if (!token) {
      throw new Error("not authenticated");
    }
    return createBasisOpenApiClient({ baseUrl: base, accessToken: token });
  }

  return {
    apiUrl,
    fetchJson,
    sessionFetch,
    authPath,
    platformPath,
    workspacePath,
    openapi: openapiClient,
    workspace(workspaceId: string) {
      const token = options.getAccessToken();
      if (!token) {
        throw new Error("not authenticated");
      }
      return createBasisClient({ baseUrl: base, accessToken: token }).workspace(workspaceId);
    },
  };
}

export type ChunkSearchResponse = {
  chunks?: unknown[];
  query?: string;
  mode?: string;
  [key: string]: unknown;
};

export type FindEntitiesResponse = {
  query: string;
  ledger_entities: unknown[];
  graph_nodes?: unknown[];
};

export type LedgerEntitiesListResponse = {
  entities: unknown[];
  total?: number;
  limit?: number;
  offset?: number;
};

export type GraphSearchResponse = {
  results: unknown[];
  engine?: string;
  at?: string;
  temporal_filter?: boolean;
};

export type McpIntegrationInfoResponse = {
  mcp_url: string;
  tools: string[];
  tool_entries?: Array<{ name: string; description: string; access?: 'read' | 'write' }>;
  http_operation_entries?: Array<{
    name: string;
    description: string;
    access?: 'read' | 'write';
    path?: string;
  }>;
  cursor_example?: {
    mcpServers: Record<string, { url: string; headers: Record<string, string> }>;
  };
  [key: string]: unknown;
};

/** Typed client for every path in the Basis OpenAPI v1 export. */
export function createBasisOpenApiClient(options: BasisClientOptions): BasisOpenApiClient {
  const base = options.baseUrl.replace(/\/$/, "");
  return createOpenApiClient<paths>({
    baseUrl: base,
    headers: { Authorization: `Bearer ${options.accessToken}` },
  });
}

/** OpenAPI client without auth (public auth routes, providers, magic-link, …). */
export function createBasisPublicOpenApiClient(
  options: BasisPublicOpenApiClientOptions = {},
): BasisOpenApiClient {
  const base = (options.baseUrl ?? "").replace(/\/$/, "");
  return createOpenApiClient<paths>({
    baseUrl: base,
    fetch: async (input: Request) => {
      const headers = new Headers(input.headers);
      options.beforeRequest?.(headers);
      return fetch(new Request(input, { headers }));
    },
  });
}

export function createBasisClient(options: BasisClientOptions) {
  const base = options.baseUrl.replace(/\/$/, "");
  const openapi = createBasisOpenApiClient(options);

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${options.accessToken}`);
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const res = await fetch(`${base}${path}`, { ...init, headers });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return (await res.json()) as T;
  }

  return {
    openapi: openapi,
    workspace(workspaceId: string) {
      const prefix = `/api/v1/workspaces/${encodeURIComponent(workspaceId)}`;
      return {
        mcpInfo: () => request<McpIntegrationInfoResponse>(`${prefix}/mcp`),
        searchChunks: (
          query: string,
          limit = 10,
          filters?: {
            as_of?: string;
            created_after?: string;
            created_before?: string;
          },
        ) => {
          const params = new URLSearchParams({ q: query, limit: String(limit) });
          if (filters?.as_of?.trim()) params.set('as_of', filters.as_of.trim());
          if (filters?.created_after?.trim()) {
            params.set('created_after', filters.created_after.trim());
          }
          if (filters?.created_before?.trim()) {
            params.set('created_before', filters.created_before.trim());
          }
          return request<ChunkSearchResponse>(`${prefix}/search?${params}`);
        },
        findEntities: (query: string, limit = 20) => {
          const params = new URLSearchParams({ q: query, limit: String(limit) });
          return request<FindEntitiesResponse>(`${prefix}/entities/find?${params}`);
        },
        listLedgerEntities: (limit = 20, offset = 0) => {
          const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset),
          });
          return request<LedgerEntitiesListResponse>(`${prefix}/ledger/entities?${params}`);
        },
        searchGraph: (
          query: string,
          limit = 20,
          options?: { at?: string; include_archived?: boolean },
        ) =>
          request<GraphSearchResponse>(`${prefix}/graph/search`, {
            method: "POST",
            body: JSON.stringify({
              query,
              limit,
              ...(options?.at ? { at: options.at } : {}),
              ...(options?.include_archived ? { include_archived: true } : {}),
            }),
          }),
      };
    },
  };
}

export type BasisClient = ReturnType<typeof createBasisClient>;
