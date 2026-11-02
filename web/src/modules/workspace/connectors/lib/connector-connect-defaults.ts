/** Default JSON templates when picking a BOCP auth mode in the connect dialog. */

export function defaultConnectorConfigForAuth(
  service: string,
  authMode: string,
): Record<string, unknown> {
  if (authMode === 'database_dsn') {
    return {
      host: 'localhost',
      port: service === 'mysql' ? 3306 : 5432,
      database: 'erp',
    };
  }
  return {};
}

export function defaultConnectorCredentialsForAuth(
  service: string,
  authMode: string,
): Record<string, string> {
  if (authMode === 'api_key') {
    if (service === 'github') {
      return { personal_access_token: '' };
    }
    return { api_key: '' };
  }
  if (authMode === 'oauth2') {
    return { access_token: '' };
  }
  if (authMode === 'database_dsn' || authMode === 'basic') {
    return { username: service === 'database_dsn' ? service : '', password: '' };
  }
  return {};
}

export function formatConnectorConnectJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2);
}

export function authModesForConnector(
  auth: Array<{ auth_mode: string }> | undefined,
): string[] {
  const modes = (auth ?? []).map((a) => a.auth_mode).filter(Boolean);
  return modes.length > 0 ? modes : ['custom'];
}
