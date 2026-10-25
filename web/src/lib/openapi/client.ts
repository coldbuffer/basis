import { createBasisPublicOpenApiClient } from '@/lib/openapi/transport.js';

import { basisApiBaseUrl } from '@/lib/openapi/basis-api-url.js';
import { basisSessionClient } from '@/lib/session/basis-session-client.js';
import { errorFromApiResponse } from '@/lib/errors/api-error.js';
import { unwrapOpenApi } from '@/lib/openapi/response.js';
import { ensureRequestIdHeader } from '@/lib/workspace/request-id.js';

let _publicOpenApi: ReturnType<typeof createBasisPublicOpenApiClient> | null = null;
let _publicOpenApiBaseUrl: string | null = null;

/** `/api/v1/workspaces/{id}/<suffix>` — workspace OpenAPI route suffix. */
export function workspaceApiPath(workspaceId: string, suffix: string): string {
  const segment = suffix.replace(/^\//, '');
  const root = `/api/v1/workspaces/${encodeURIComponent(workspaceId)}`;
  return segment ? `${root}/${segment}` : root;
}

/** Unauthenticated OpenAPI client (login providers, magic-link, …). */
export function publicOpenApi() {
  const baseUrl = basisApiBaseUrl();
  if (!_publicOpenApi || _publicOpenApiBaseUrl !== baseUrl) {
    _publicOpenApiBaseUrl = baseUrl;
    _publicOpenApi = createBasisPublicOpenApiClient({
      baseUrl,
      beforeRequest: ensureRequestIdHeader,
    });
  }
  return _publicOpenApi;
}

/** Session-authenticated typed OpenAPI client (`openapi-fetch`). */
export function openApi() {
  return basisSessionClient().openapi();
}

export type OpenApiInit = {
  params?: {
    path?: Record<string, string>;
    query?: Record<string, unknown>;
  };
  body?: unknown;
  signal?: AbortSignal;
  /** For `workspaceOpenApiResponse` only; default `stream` leaves the body for caller `.json()` / `.blob()`. */
  parseAs?: 'json' | 'blob' | 'text' | 'arrayBuffer' | 'stream';
};

function workspaceOpenApiPath(suffix: string): string {
  const segment = suffix.replace(/^\//, '');
  return segment ? `/api/v1/workspaces/{workspace_id}/${segment}` : `/api/v1/workspaces/{workspace_id}`;
}

function workspaceOpenApiInit(workspaceId: string, init?: OpenApiInit): OpenApiInit {
  return {
    ...init,
    params: {
      ...init?.params,
      path: { workspace_id: workspaceId, ...(init?.params?.path ?? {}) },
    },
  };
}

function openApiRequestOptions(init?: OpenApiInit) {
  return {
    ...init,
    signal: init?.signal,
    parseAs: init?.parseAs ?? 'json',
  };
}

function workspaceOpenApiRawResponseOptions(init?: OpenApiInit) {
  return {
    ...init,
    signal: init?.signal,
    parseAs: init?.parseAs ?? 'stream',
  };
}

type OpenApiMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/** Low-level workspace OpenAPI call returning the raw `Response` (blob, 207, multipart). */
export async function workspaceOpenApiResponse(
  method: OpenApiMethod,
  workspaceId: string,
  suffix: string,
  init?: OpenApiInit,
): Promise<Response> {
  const path = workspaceOpenApiPath(suffix);
  const merged = workspaceOpenApiRawResponseOptions(workspaceOpenApiInit(workspaceId, init));
  const client = openApi();
  const result = (method === 'GET'
    ? await client.GET(path as never, merged as never)
    : method === 'POST'
      ? await client.POST(path as never, merged as never)
      : method === 'PUT'
        ? await client.PUT(path as never, merged as never)
        : method === 'PATCH'
          ? await client.PATCH(path as never, merged as never)
          : await client.DELETE(path as never, merged as never)) as {
    error?: unknown;
    response: Response;
  };
  if (result.error !== undefined) {
    throw errorFromApiResponse(result.response.status, result.error);
  }
  return result.response;
}

export async function openApiGET<T>(path: string, init?: OpenApiInit): Promise<T> {
  return unwrapOpenApi(
    await openApi().GET(path as never, openApiRequestOptions(init) as never),
  ) as T;
}

export async function openApiPOST<T>(path: string, init?: OpenApiInit): Promise<T> {
  return unwrapOpenApi(
    await openApi().POST(path as never, openApiRequestOptions(init) as never),
  ) as T;
}

export async function openApiPUT<T>(path: string, init?: OpenApiInit): Promise<T> {
  return unwrapOpenApi(
    await openApi().PUT(path as never, openApiRequestOptions(init) as never),
  ) as T;
}

export async function openApiPATCH<T>(path: string, init?: OpenApiInit): Promise<T> {
  return unwrapOpenApi(
    await openApi().PATCH(path as never, openApiRequestOptions(init) as never),
  ) as T;
}

export async function openApiDELETE(path: string, init?: OpenApiInit): Promise<void> {
  unwrapOpenApi(await openApi().DELETE(path as never, openApiRequestOptions(init) as never));
}

export async function publicOpenApiGET<T>(path: string, init?: OpenApiInit): Promise<T> {
  return unwrapOpenApi(
    await publicOpenApi().GET(path as never, openApiRequestOptions(init) as never),
  ) as T;
}

export async function publicOpenApiPOST<T>(path: string, init?: OpenApiInit): Promise<T> {
  return unwrapOpenApi(
    await publicOpenApi().POST(path as never, openApiRequestOptions(init) as never),
  ) as T;
}

/** Workspace sub-route: `/api/v1/workspaces/{workspace_id}/<suffix>` with path param binding. */
export async function workspaceOpenApiGET<T>(
  workspaceId: string,
  suffix: string,
  init?: OpenApiInit,
): Promise<T> {
  return openApiGET<T>(workspaceOpenApiPath(suffix), workspaceOpenApiInit(workspaceId, init));
}

export async function workspaceOpenApiPOST<T>(
  workspaceId: string,
  suffix: string,
  init?: OpenApiInit,
): Promise<T> {
  return openApiPOST<T>(workspaceOpenApiPath(suffix), workspaceOpenApiInit(workspaceId, init));
}

export async function workspaceOpenApiPUT<T>(
  workspaceId: string,
  suffix: string,
  init?: OpenApiInit,
): Promise<T> {
  return openApiPUT<T>(workspaceOpenApiPath(suffix), workspaceOpenApiInit(workspaceId, init));
}

export async function workspaceOpenApiPATCH<T>(
  workspaceId: string,
  suffix: string,
  init?: OpenApiInit,
): Promise<T> {
  return openApiPATCH<T>(workspaceOpenApiPath(suffix), workspaceOpenApiInit(workspaceId, init));
}

export async function workspaceOpenApiDELETE(
  workspaceId: string,
  suffix: string,
  init?: OpenApiInit,
): Promise<void> {
  return openApiDELETE(workspaceOpenApiPath(suffix), workspaceOpenApiInit(workspaceId, init));
}
