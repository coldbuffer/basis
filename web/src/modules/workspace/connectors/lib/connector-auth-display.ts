import type { ConnectorAuthCatalogEntry } from '@/modules/workspace/connectors/lib/connector-auth-fields.js';

export type { ConnectorAuthCatalogEntry };

/** Labels for BOCP AuthModeLiteral when manifest auth.display_name is omitted. */
export type ConnectorAuthModeLabels = Record<string, string>;

export function connectorAuthCatalogEntries(
  auth: ConnectorAuthCatalogEntry[] | undefined,
): ConnectorAuthCatalogEntry[] {
  if (!auth?.length) {
    return [{ auth_mode: 'custom' }];
  }
  return auth;
}

export function authModeDisplayLabel(
  authMode: string,
  manifestDisplayName: string | null | undefined,
  fallbackLabels: ConnectorAuthModeLabels,
): string {
  const fromManifest = manifestDisplayName?.trim();
  if (fromManifest) {
    return fromManifest;
  }
  return fallbackLabels[authMode] ?? authMode;
}

export function findAuthCatalogEntry(
  auth: ConnectorAuthCatalogEntry[] | undefined,
  authMode: string,
): ConnectorAuthCatalogEntry | undefined {
  return connectorAuthCatalogEntries(auth).find((entry) => entry.auth_mode === authMode);
}
