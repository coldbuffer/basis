/** Integration playground OAuth helpers (copy; shares storage keys with connectors callback route). */

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

export type PlaygroundPendingOAuth = {
  workspaceId: string;
  service: string;
  connectionConfig: Record<string, unknown>;
  state: string;
  redirectUri: string;
  codeVerifier?: string;
  endUserSubjectId?: string;
  returnTo?: 'connectors-catalog' | 'integration-connectors';
};

export function workspacePlaygroundOAuthRedirectUri(workspaceId: string): string {
  if (typeof window === 'undefined') {
    return `/workspaces/${workspaceId}/connectors/oauth/callback`;
  }
  return `${window.location.origin}/workspaces/${workspaceId}/connectors/oauth/callback`;
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

export async function generatePkcePair(): Promise<{ verifier: string; challenge: string }> {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  const verifier = base64UrlEncode(bytes);
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  const challenge = base64UrlEncode(new Uint8Array(digest));
  return { verifier, challenge };
}

export function savePlaygroundPendingOAuth(pending: PlaygroundPendingOAuth): void {
  writeOAuthStorageItem(PENDING_KEY, JSON.stringify(pending));
  if (pending.codeVerifier) {
    writeOAuthStorageItem(PKCE_KEY_PREFIX + pending.state, pending.codeVerifier);
  }
}

export function connectorAuthNeedsPkce(
  auth: Array<{ auth_mode?: string; oauth2?: { pkce_s256?: boolean } }> | undefined,
): boolean {
  if (!auth?.length) return false;
  return auth.some((entry) => entry.auth_mode === 'oauth2' && entry.oauth2?.pkce_s256 === true);
}
