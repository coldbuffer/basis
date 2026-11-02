/** Action kinds for workspace app card connection controls. */

import { connectorAuthCatalogEntries } from '@/modules/workspace/connectors/lib/connector-auth-display.js';
import type { ConnectorAuthCatalogEntry } from '@/modules/workspace/connectors/lib/connector-auth-fields.js';

export type WorkspaceAppConnectionAction =
  | 'none'
  | 'configure_connection'
  | 'manage_connection'
  | 'authorize'
  | 'reauthorize';

type AuthCarrier = {
  auth?: ConnectorAuthCatalogEntry[];
};

export function catalogProviderNeedsCredentials(item: AuthCarrier): boolean {
  const entries = connectorAuthCatalogEntries(item.auth);
  if (entries.length === 0) {
    return true;
  }
  return entries.some((entry) => entry.auth_mode !== 'none');
}

export function catalogProviderSupportsOAuth(item: AuthCarrier): boolean {
  return connectorAuthCatalogEntries(item.auth).some(
    (entry) => entry.auth_mode === 'oauth2' || entry.auth_mode === 'oauth2_cc',
  );
}

/** User-token OAuth (e.g. GitHub) vs vault credential connectors (e.g. MySQL). */
export function catalogProviderUsesOAuthUserAuthorization(item: AuthCarrier): boolean {
  const modes = connectorAuthCatalogEntries(item.auth).map((entry) => entry.auth_mode);
  const credentialModes = modes.filter(
    (mode) => mode !== 'none' && mode !== 'oauth2' && mode !== 'oauth2_cc',
  );
  if (credentialModes.length > 0) {
    return false;
  }
  return modes.some((mode) => mode === 'oauth2' || mode === 'oauth2_cc');
}

export function resolveWorkspaceAppConnectionAction(
  item: AuthCarrier,
  connectionCount: number,
): WorkspaceAppConnectionAction {
  if (!catalogProviderNeedsCredentials(item)) {
    return 'none';
  }
  const hasConnection = connectionCount > 0;
  if (catalogProviderUsesOAuthUserAuthorization(item)) {
    return 'none';
  }
  return hasConnection ? 'manage_connection' : 'configure_connection';
}
