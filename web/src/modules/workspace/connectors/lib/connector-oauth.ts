const PENDING_KEY = 'basis_bocp_oauth_pending';
const PKCE_KEY_PREFIX = 'basis_bocp_oauth_pkce:';

function readOAuthStorageItem(key: string): string | null {
  try {
    return localStorage.getItem(key) ?? sessionStorage.getItem(key);
  } catch {
    try {
      return sessionStorage.getItem(key);
    } catch {
      return null;
    }
  }
}

function writeOAuthStorageItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

function removeOAuthStorageItem(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

export type PendingConnectorOAuth = {
  workspaceId: string;
  service: string;
    connectionConfig: Record<string, unknown>;
  state: string;
  redirectUri: string;
  codeVerifier?: string;
  /** When set, authorize/exchange use Integration API for end_user connections. */
  endUserSubjectId?: string;
  /** Post-success navigation (default: connectors catalog). */
  returnTo?: 'connectors-catalog' | 'connectors-authorization' | 'integration-connectors';
};

export function workspaceConnectorOAuthCallbackPath(workspaceId: string): string {
  return `/workspaces/${workspaceId}/connectors/oauth/callback`;
}

export function workspaceConnectorOAuthRedirectUri(workspaceId: string): string {
  if (typeof window === 'undefined') {
    return workspaceConnectorOAuthCallbackPath(workspaceId);
  }
  return `${window.location.origin}${workspaceConnectorOAuthCallbackPath(workspaceId)}`;
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

export function generateOAuthState(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

export async function generatePkcePair(): Promise<{ verifier: string; challenge: string }> {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  const verifier = base64UrlEncode(bytes);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  const challenge = base64UrlEncode(new Uint8Array(digest));
  return { verifier, challenge };
}

export function savePendingConnectorOAuth(pending: PendingConnectorOAuth): void {
  writeOAuthStorageItem(PENDING_KEY, JSON.stringify(pending));
  if (pending.codeVerifier) {
    writeOAuthStorageItem(PKCE_KEY_PREFIX + pending.state, pending.codeVerifier);
  }
}

export function readPkceVerifierForOAuthState(state: string): string | undefined {
  return readOAuthStorageItem(PKCE_KEY_PREFIX + state) ?? undefined;
}

/** Client-side check for connector embed packed OAuth state (v1). */
export function tryParseConnectorOAuthState(
  state: string,
): { service: string; subject_id: string } | null {
  try {
    const padded = state.replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(padded.padEnd(padded.length + ((4 - (padded.length % 4)) % 4), '='));
    const parsed = JSON.parse(json) as { v?: number; service?: string; subject_id?: string };
    if (parsed.v !== 1 || !parsed.service || !parsed.subject_id) {
      return null;
    }
    return { service: parsed.service, subject_id: parsed.subject_id };
  } catch {
    return null;
  }
}

/** Resolve pending session for OAuth callback (tolerates packed state rotation). */
export function resolveOAuthCallbackPending(
  workspaceId: string,
  state: string,
): PendingConnectorOAuth | null {
  const pending = readPendingConnectorOAuth();
  if (pending && pending.workspaceId === workspaceId) {
    if (pending.state === state) {
      const verifier = pending.codeVerifier ?? readPkceVerifierForOAuthState(state);
      return verifier ? { ...pending, codeVerifier: verifier } : pending;
    }
    if (pending.endUserSubjectId) {
      const parsed = tryParseConnectorOAuthState(state);
      if (
        parsed &&
        parsed.service === pending.service &&
        parsed.subject_id === pending.endUserSubjectId
      ) {
        const verifier = readPkceVerifierForOAuthState(state) ?? pending.codeVerifier;
        if (verifier) {
          return { ...pending, state, codeVerifier: verifier };
        }
      }
    } else {
      return null;
    }
  }

  const parsed = tryParseConnectorOAuthState(state);
  if (!parsed) {
    return null;
  }
  const verifier = readPkceVerifierForOAuthState(state);
  if (!verifier) {
    return null;
  }
  return {
    workspaceId,
    service: parsed.service,
        connectionConfig: {},
    state,
    redirectUri: workspaceConnectorOAuthRedirectUri(workspaceId),
    codeVerifier: verifier,
    endUserSubjectId: parsed.subject_id,
    returnTo: 'integration-connectors',
  };
}

export function readPendingConnectorOAuth(): PendingConnectorOAuth | null {
  try {
    const raw = readOAuthStorageItem(PENDING_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PendingConnectorOAuth;
  } catch {
    return null;
  }
}

export function clearPendingConnectorOAuth(callbackState?: string): void {
  const pending = readPendingConnectorOAuth();
  removeOAuthStorageItem(PENDING_KEY);
  if (pending?.state) {
    removeOAuthStorageItem(PKCE_KEY_PREFIX + pending.state);
  }
  if (callbackState && callbackState !== pending?.state) {
    removeOAuthStorageItem(PKCE_KEY_PREFIX + callbackState);
  }
}

const oauthExchangeInflight = new Map<string, Promise<void>>();

/** Deduplicate OAuth code exchange (e.g. React Strict Mode double effects). */
export function runOAuthCodeExchangeOnce(
  workspaceId: string,
  code: string,
  run: () => Promise<void>,
): Promise<void> {
  const key = `${workspaceId}:${code}`;
  const existing = oauthExchangeInflight.get(key);
  if (existing) {
    return existing;
  }
  const promise = run().finally(() => {
    oauthExchangeInflight.delete(key);
  });
  oauthExchangeInflight.set(key, promise);
  return promise;
}

export function connectorAuthNeedsPkce(
  auth: Array<{ auth_mode?: string; oauth2?: { pkce_s256?: boolean } }> | undefined,
): boolean {
  if (!auth?.length) return false;
  return auth.some((entry) => entry.auth_mode === 'oauth2' && entry.oauth2?.pkce_s256 === true);
}
