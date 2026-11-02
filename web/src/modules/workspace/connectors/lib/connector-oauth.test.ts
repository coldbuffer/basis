import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  connectorAuthNeedsPkce,
  resolveOAuthCallbackPending,
  savePendingConnectorOAuth,
  tryParseConnectorOAuthState,
} from '@/modules/workspace/connectors/lib/connector-oauth.js';

const PACKED_GITHUB_STATE =
  'eyJ2IjoxLCJzZXJ2aWNlIjoiZ2l0aHViIiwic3ViamVjdF9pZCI6InVzZXItMSIsIm4iOiI3NzQwNzk2NDUxNGQifQ==';

function mockWebStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => [...map.keys()][index] ?? null,
    removeItem: (key: string) => {
      map.delete(key);
    },
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
  };
}

beforeEach(() => {
  vi.stubGlobal('localStorage', mockWebStorage());
  vi.stubGlobal('sessionStorage', mockWebStorage());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('connectorAuthNeedsPkce', () => {
  it('returns true when oauth2 auth spec requires PKCE', () => {
    expect(
      connectorAuthNeedsPkce([{ auth_mode: 'oauth2', oauth2: { pkce_s256: true } }]),
    ).toBe(true);
  });

  it('returns false for api_key or oauth2 without pkce', () => {
    expect(connectorAuthNeedsPkce([{ auth_mode: 'api_key' }])).toBe(false);
    expect(connectorAuthNeedsPkce([{ auth_mode: 'oauth2', oauth2: { pkce_s256: false } }])).toBe(
      false,
    );
  });
});

describe('tryParseConnectorOAuthState', () => {
  it('parses packed v1 state from the API', () => {
    expect(tryParseConnectorOAuthState(PACKED_GITHUB_STATE)).toEqual({
      service: 'github',
      subject_id: 'user-1',
    });
  });
});

describe('resolveOAuthCallbackPending', () => {
  it('matches integration pending when callback state equals saved state', () => {
    savePendingConnectorOAuth({
      workspaceId: 'ws-1',
      service: 'github',
            connectionConfig: {},
      state: PACKED_GITHUB_STATE,
      redirectUri: 'http://localhost/cb',
      codeVerifier: 'verifier-abc',
      endUserSubjectId: 'user-1',
      returnTo: 'integration-connectors',
    });
    const resolved = resolveOAuthCallbackPending('ws-1', PACKED_GITHUB_STATE);
    expect(resolved?.codeVerifier).toBe('verifier-abc');
    expect(resolved?.endUserSubjectId).toBe('user-1');
  });

  it('recovers integration flow from PKCE + packed state when pending JSON is missing', () => {
    localStorage.setItem('basis_bocp_oauth_pkce:' + PACKED_GITHUB_STATE, 'verifier-only');
    const resolved = resolveOAuthCallbackPending('ws-1', PACKED_GITHUB_STATE);
    expect(resolved?.service).toBe('github');
    expect(resolved?.codeVerifier).toBe('verifier-only');
  });
});
