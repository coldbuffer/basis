export type ConnectorAuthFieldSpec = {
  key: string;
  label: string;
  input_type?: string | null;
  required?: boolean;
  secret?: boolean;
  description?: string | null;
  placeholder?: string | null;
  default?: string | number | boolean | null;
};

export type ConnectorAuthCatalogEntry = {
  auth_mode: string;
  display_name?: string | null;
  oauth2?: { pkce_s256?: boolean };
  connection_config?: ConnectorAuthFieldSpec[];
  credentials?: ConnectorAuthFieldSpec[];
};

export function authFieldDefaultValues(
  fields: ConnectorAuthFieldSpec[] | undefined,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fields ?? []) {
    const d = field.default;
    out[field.key] = d === undefined || d === null ? '' : String(d);
  }
  return out;
}

/** Merge catalog field defaults with a saved connection_config / credentials object. */
export function authFieldValuesFromObject(
  fields: ConnectorAuthFieldSpec[] | undefined,
  source: Record<string, unknown> | undefined,
): Record<string, string> {
  const out = authFieldDefaultValues(fields);
  if (!source) {
    return out;
  }
  for (const field of fields ?? []) {
    const value = source[field.key];
    if (value === undefined || value === null) {
      continue;
    }
    out[field.key] = String(value);
  }
  return out;
}

export function authCredentialFieldsAreBlank(
  fields: ConnectorAuthFieldSpec[] | undefined,
  values: Record<string, string>,
): boolean {
  for (const field of fields ?? []) {
    if ((values[field.key] ?? '').trim()) {
      return false;
    }
  }
  return true;
}

export function parsedCredentialJsonIsBlank(json: string): boolean {
  try {
    const parsed = JSON.parse(json || '{}') as Record<string, unknown>;
    return Object.values(parsed).every(
      (v) => v === undefined || v === null || String(v).trim() === '',
    );
  } catch {
    return false;
  }
}

export function hasStructuredAuthForm(entry: ConnectorAuthCatalogEntry | undefined): boolean {
  if (!entry) return false;
  return Boolean(entry.connection_config?.length || entry.credentials?.length);
}

/** OAuth2 catalog entry with no connection_config / credentials fields (e.g. GitHub OAuth). */
export function isOAuth2ConnectManifestOnly(entry: ConnectorAuthCatalogEntry | undefined): boolean {
  if (!entry || entry.auth_mode !== 'oauth2') {
    return false;
  }
  return !hasStructuredAuthForm(entry);
}

export function buildObjectFromAuthFields(
  fields: ConnectorAuthFieldSpec[] | undefined,
  values: Record<string, string>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const field of fields ?? []) {
    const raw = values[field.key] ?? '';
    if (!raw && field.required === false) {
      continue;
    }
    if (field.input_type === 'number') {
      const n = Number(raw);
      out[field.key] = Number.isFinite(n) ? n : raw;
    } else {
      out[field.key] = raw;
    }
  }
  return out;
}
