/** Detect `{{config.key}}` / `{{key}}` placeholders used as BOCP stream_params. */

const PLACEHOLDER_RE = /\{\{config\.([a-zA-Z0-9_]+)\}\}|\{\{([a-zA-Z0-9_]+)\}\}/g;

const RESERVED_KEYS = new Set([
  'patch',
  'external_id',
  'connectionConfig',
  'credentials',
  'config',
]);

export type ManifestStreamSnippet = {
  name?: string;
  retriever?: {
    path?: string;
    path_template?: string;
    request_params?: Record<string, unknown>;
    request_headers?: Record<string, unknown>;
  };
  mutations?: Record<
    string,
    {
      path_template?: string;
      body_template?: unknown;
    }
  >;
};

function collectFromString(template: string, keys: Set<string>) {
  for (const match of template.matchAll(PLACEHOLDER_RE)) {
    const key = match[1] ?? match[2];
    if (key && !RESERVED_KEYS.has(key)) {
      keys.add(key);
    }
  }
}

function collectFromUnknown(value: unknown, keys: Set<string>) {
  if (typeof value === 'string') {
    collectFromString(value, keys);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      collectFromUnknown(item, keys);
    }
    return;
  }
  if (value && typeof value === 'object') {
    for (const nested of Object.values(value as Record<string, unknown>)) {
      collectFromUnknown(nested, keys);
    }
  }
}

export function extractStreamParamKeysFromStream(stream: ManifestStreamSnippet | undefined): string[] {
  if (!stream) {
    return [];
  }
  const keys = new Set<string>();
  const retriever = stream.retriever;
  if (retriever?.path) {
    collectFromString(retriever.path, keys);
  }
  if (retriever?.path_template) {
    collectFromString(retriever.path_template, keys);
  }
  collectFromUnknown(retriever?.request_params, keys);
  collectFromUnknown(retriever?.request_headers, keys);
  for (const mutation of Object.values(stream.mutations ?? {})) {
    if (mutation.path_template) {
      collectFromString(mutation.path_template, keys);
    }
    collectFromUnknown(mutation.body_template, keys);
  }
  return [...keys].sort();
}

export function streamParamsFromFieldMap(fields: Record<string, string>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, raw] of Object.entries(fields)) {
    const value = raw.trim();
    if (value) {
      out[key] = value;
    }
  }
  return out;
}

export function fieldMapFromStreamParams(params: Record<string, unknown> | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!params) {
    return out;
  }
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined) {
      continue;
    }
    out[key] = typeof value === 'string' ? value : JSON.stringify(value);
  }
  return out;
}

export function mergeStreamParamFieldMap(
  keys: string[],
  existing: Record<string, string>,
): Record<string, string> {
  const next: Record<string, string> = {};
  for (const key of keys) {
    next[key] = existing[key] ?? '';
  }
  for (const [key, value] of Object.entries(existing)) {
    if (!(key in next) && value.trim()) {
      next[key] = value;
    }
  }
  return next;
}
