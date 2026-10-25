import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";
import { fmt } from "@/i18n/format.js";
import { localeFromBrowser, type Locale } from "@/i18n/locale.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";
import { errorFromApiResponse } from "@/lib/errors/api-error.js";
import { basisApiUrl } from "@/lib/session/basis-session-fetch.js";
import { basisSessionClient } from "@/lib/session/basis-session-client.js";
import { workspaceOpenApiResponse } from "@/lib/openapi/client.js";
import { isWorkspaceScopedApiPath, workspaceApiRoot } from "@/lib/workspace/api-path.js";
import { ensureRequestIdHeader } from "@/lib/workspace/request-id.js";

export type WorkspaceHttpConfig = {
  /**
   * Workspace-scoped API root, e.g. `/api/v1/workspaces/{workspace_id}`.
   * Rewrites vendored `/api/graph/...` paths to `${apiRoot}/graph/...`.
   */
  apiRoot?: string;
  getAuthHeaders?: () => HeadersInit;
  /** Basis: ticketed workspace WebSocket via `buildWorkspaceHttpConfig`. */
  openGraphUpdatesSocket?: () => Promise<WebSocket>;
};

function wsHttpLocale(locale?: Locale): Locale {
  if (locale) {
    return locale;
  }
  const lang = typeof navigator !== "undefined" ? navigator.language : "en";
  return localeFromBrowser(lang);
}

function workspaceContextRequiredMessage(locale?: Locale): string {
  return messagesForLocale(wsHttpLocale(locale)).core.workspace_runtime.workspace_context_required;
}

function requestFailedMessage(status: number, locale?: Locale): string {
  return fmt(messagesForLocale(wsHttpLocale(locale)).core.common.requestFailedStatus, {
    status,
  });
}

export function assertWorkspaceHttpContext(): void {
  const { apiRoot } = activeConfig;
  if (!apiRoot) {
    throw new Error(workspaceContextRequiredMessage());
  }
}

const WorkspaceHttpContext = createContext<WorkspaceHttpConfig>({});

let activeConfig: WorkspaceHttpConfig = {};

export function setActiveWorkspaceHttpConfig(config: WorkspaceHttpConfig): void {
  activeConfig = config;
}

export function getActiveWorkspaceHttpConfig(): WorkspaceHttpConfig {
  return activeConfig;
}

export function resolveWorkspaceApiUrl(pathOrUrl: string): string {
  const { apiRoot } = activeConfig;
  if (
    !apiRoot &&
    pathOrUrl.startsWith("/api/") &&
    !isWorkspaceScopedApiPath(pathOrUrl)
  ) {
    throw new Error(workspaceContextRequiredMessage());
  }
  if (!apiRoot) {
    return pathOrUrl;
  }

  try {
    if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) {
      const url = new URL(pathOrUrl);
      if (url.pathname.startsWith("/api/")) {
        url.pathname = rewriteApiPath(url.pathname, apiRoot);
      }
      return url.toString();
    }
  } catch {
    return pathOrUrl;
  }

  if (pathOrUrl.startsWith("/api/")) {
    const [pathname, query = ""] = pathOrUrl.split("?");
    const rewritten = rewriteApiPath(pathname, apiRoot);
    return query ? `${rewritten}?${query}` : rewritten;
  }

  return pathOrUrl;
}

function normalizeRoot(apiRoot: string): string {
  return apiRoot.endsWith("/") ? apiRoot.slice(0, -1) : apiRoot;
}

/** Workspace-scoped API path (`/api/v1/workspaces/{id}/...`). Requires `workspaceId` or active `apiRoot`. */
export function buildWorkspaceApiPath(subpath: string, workspaceId?: string): string {
  const segment = subpath.replace(/^\//, "");
  if (workspaceId) {
    return `${workspaceApiRoot(workspaceId)}/${segment}`;
  }
  const { apiRoot } = getActiveWorkspaceHttpConfig();
  if (apiRoot) {
    return `${normalizeRoot(apiRoot)}/${segment}`;
  }
  throw new Error(workspaceContextRequiredMessage());
}

/** Graph routes under `/api/v1/workspaces/{id}/graph/...`. */
export function buildWorkspaceGraphApiPath(resource: string, workspaceId?: string): string {
  const segment = resource.replace(/^\//, "");
  return buildWorkspaceApiPath(`graph/${segment}`, workspaceId);
}

function rewriteApiPath(pathname: string, apiRoot: string): string {
  const root = normalizeRoot(apiRoot);
  if (pathname === root || pathname.startsWith(`${root}/`)) {
    return pathname;
  }
  // Already workspace-scoped (Basis or another host); do not prepend apiRoot again.
  if (isWorkspaceScopedApiPath(pathname)) {
    return pathname;
  }
  if (!pathname.startsWith("/api/")) {
    return pathname;
  }
  const suffix = pathname.slice("/api".length);
  return `${root}${suffix}`;
}

/** Map a resolved workspace URL to an `/api/...` path for the OpenAPI session transport. */
function sessionPathFromResolvedUrl(resolved: string): string {
  const absolute =
    resolved.startsWith("http://") || resolved.startsWith("https://")
      ? resolved
      : basisApiUrl(resolved);
  const base = basisSessionClient().apiUrl("");
  if (base && absolute.startsWith(base)) {
    const rest = absolute.slice(base.length);
    return rest.startsWith("/") ? rest : `/${rest}`;
  }
  try {
    const url = new URL(absolute);
    return `${url.pathname}${url.search}`;
  } catch {
    return absolute.startsWith("/") ? absolute : `/${absolute}`;
  }
}

function parseWorkspaceOpenApiRequest(pathWithQuery: string): {
  workspaceId: string;
  suffix: string;
  query: Record<string, string>;
} | null {
  const [pathname, search = ""] = pathWithQuery.split("?");
  const match = pathname.match(/^\/api\/v1\/workspaces\/([^/]+)\/(.+)$/);
  if (!match) {
    return null;
  }
  const query: Record<string, string> = {};
  if (search) {
    new URLSearchParams(search).forEach((value, key) => {
      query[key] = value;
    });
  }
  return {
    workspaceId: decodeURIComponent(match[1]!),
    suffix: match[2]!,
    query,
  };
}

/**
 * @deprecated Prefer `workspaceOpenApiGET` / `workspaceOpenApiPOST` / `workspaceOpenApiResponse`.
 * Workspace routes are executed via the OpenAPI session client (`openapi-fetch`).
 */
export async function workspaceFetch(
  input: string | URL,
  init?: RequestInit,
): Promise<Response> {
  const url =
    typeof input === "string"
      ? resolveWorkspaceApiUrl(input)
      : resolveWorkspaceApiUrl(input.toString());
  const path = sessionPathFromResolvedUrl(url);
  const parsed = parseWorkspaceOpenApiRequest(path);
  const method = (init?.method ?? "GET").toUpperCase();
  if (
    parsed &&
    (method === "GET" || method === "POST" || method === "PUT" || method === "PATCH" || method === "DELETE")
  ) {
    return workspaceOpenApiResponse(
      method as "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
      parsed.workspaceId,
      parsed.suffix,
      {
        params: Object.keys(parsed.query).length ? { query: parsed.query } : undefined,
        body:
          method === "GET" || method === "DELETE"
            ? undefined
            : init?.body,
        signal: init?.signal ?? undefined,
      },
    );
  }
  const headers = new Headers(init?.headers);
  ensureRequestIdHeader(headers);
  const auth = activeConfig.getAuthHeaders?.();
  if (auth) {
    new Headers(auth).forEach((value, key) => {
      if (!headers.has(key)) {
        headers.set(key, value);
      }
    });
  }
  return basisSessionClient().sessionFetch(path, { ...init, headers });
}

/** Workspace-scoped fetch with auth, request ID, and coded API errors (X-01). */
export async function workspaceFetchJson<T = unknown>(
  input: string | URL,
  init?: RequestInit,
  fallbackMessage?: string,
  locale?: Locale,
): Promise<T> {
  const response = await workspaceFetch(input, init);
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => ({}))
    : await response.text().catch(() => "");
  if (!response.ok) {
    throw errorFromApiResponse(
      response.status,
      payload,
      fallbackMessage ?? requestFailedMessage(response.status, locale),
    );
  }
  return payload as T;
}

export async function openGraphUpdatesWebSocket(locale?: Locale): Promise<WebSocket> {
  if (activeConfig.openGraphUpdatesSocket) {
    return activeConfig.openGraphUpdatesSocket();
  }
  throw new Error(
    messagesForLocale(wsHttpLocale(locale)).core.workspace_runtime.graph_updates_web_socket_required,
  );
}

export function WorkspaceHostProvider({
  config,
  children,
}: {
  config: WorkspaceHttpConfig;
  children: ReactNode;
}) {
  const value = useMemo(
    () => config,
    [config.apiRoot, config.getAuthHeaders, config.openGraphUpdatesSocket],
  );

  // Set before child queries run (useEffect is too late for useLoadGraph on mount).
  setActiveWorkspaceHttpConfig(value);

  useEffect(() => {
    setActiveWorkspaceHttpConfig(value);
  }, [value]);

  return (
    <WorkspaceHttpContext.Provider value={value}>{children}</WorkspaceHttpContext.Provider>
  );
}

export function useWorkspaceHttpConfig(): WorkspaceHttpConfig {
  return useContext(WorkspaceHttpContext);
}
