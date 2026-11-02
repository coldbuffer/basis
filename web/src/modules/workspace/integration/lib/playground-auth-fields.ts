/** Integration playground copy of connector auth field helpers (not shared with `modules/connectors`). */

export type PlaygroundAuthFieldSpec = {
  key: string;
  label: string;
  input_type?: string | null;
  required?: boolean;
  secret?: boolean;
  description?: string | null;
  placeholder?: string | null;
  default?: string | number | boolean | null;
};

export type PlaygroundAuthCatalogEntry = {
  auth_mode: string;
  display_name?: string | null;
  oauth2?: { pkce_s256?: boolean };
  connection_config?: PlaygroundAuthFieldSpec[];
  credentials?: PlaygroundAuthFieldSpec[];
};

export function authFieldDefaultValues(
  fields: PlaygroundAuthFieldSpec[] | undefined,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fields ?? []) {
    const d = field.default;
    out[field.key] = d === undefined || d === null ? '' : String(d);
  }
  return out;
}

export function authFieldValuesFromObject(
  fields: PlaygroundAuthFieldSpec[] | undefined,
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

export function hasStructuredAuthForm(entry: PlaygroundAuthCatalogEntry | undefined): boolean {
  if (!entry) return false;
  return Boolean(entry.connection_config?.length || entry.credentials?.length);
}

export function buildObjectFromAuthFields(
  fields: PlaygroundAuthFieldSpec[] | undefined,
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
