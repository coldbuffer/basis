import type { PlaygroundAuthCatalogEntry } from '@/modules/workspace/integration/lib/playground-auth-fields.js';

export type PlaygroundAuthModeLabels = Record<string, string>;

export function connectorAuthCatalogEntries(
  auth: PlaygroundAuthCatalogEntry[] | undefined,
): PlaygroundAuthCatalogEntry[] {
  if (!auth?.length) {
    return [{ auth_mode: 'custom' }];
  }
  return auth;
}

export function authModeDisplayLabel(
  authMode: string,
  manifestDisplayName: string | null | undefined,
  fallbackLabels: PlaygroundAuthModeLabels,
): string {
  const fromManifest = manifestDisplayName?.trim();
  if (fromManifest) {
    return fromManifest;
  }
  return fallbackLabels[authMode] ?? authMode;
}

export function findAuthCatalogEntry(
  auth: PlaygroundAuthCatalogEntry[] | undefined,
  authMode: string,
): PlaygroundAuthCatalogEntry | undefined {
  return connectorAuthCatalogEntries(auth).find((entry) => entry.auth_mode === authMode);
}
