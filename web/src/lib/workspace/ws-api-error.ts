import { fmt } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import { errorFromApiResponse } from '@/lib/errors/api-error.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';

function wsCommonMessages(locale: Locale = 'en') {
  return messagesForLocale(locale).core.common;
}

export type WsJsonBody = { message?: string };

export async function throwIfWsNotOk(
  response: Response,
  fallbackMessage?: string,
): Promise<void> {
  if (response.ok) {
    return;
  }
  const data = await response.json().catch(() => ({}));
  throw errorFromApiResponse(response.status, data, fallbackMessage);
}

export async function parseWsJson<T>(
  response: Response,
  fallbackMessage?: string,
): Promise<T> {
  await throwIfWsNotOk(response, fallbackMessage);
  return (await response.json()) as T;
}

/** Workspace screens are English-first; console shell pages pass locale explicitly. */
export function wsApiErrorMessage(err: unknown, locale: Locale = 'en'): string {
  return formatUserFacingApiError(err, locale);
}

export function wsPartialSuccessWarning(
  response: Response,
  data: unknown,
  fallback: string,
): string | null {
  if (response.status !== 207) {
    return null;
  }
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const message = (data as WsJsonBody).message?.trim();
    if (message) {
      return message;
    }
  }
  return fallback;
}

export async function wsGetJson<T>(
  workspaceId: string,
  apiSuffix: string,
  options?: {
    signal?: AbortSignal;
    query?: Record<string, unknown>;
    fallbackMessage?: string;
    partialWarning?: string;
    locale?: Locale;
  },
): Promise<{ data: T; partialWarning: string | null }> {
  const response = await workspaceOpenApiResponse('GET', workspaceId, apiSuffix, {
    signal: options?.signal,
    params: options?.query ? { query: options.query } : undefined,
  });
  const locale = options?.locale ?? 'en';
  const common = wsCommonMessages(locale);
  const fallback =
    options?.fallbackMessage ?? fmt(common.requestFailedStatus, { status: response.status });
  const data = await parseWsJson<T>(response, fallback);
  return {
    data,
    partialWarning: wsPartialSuccessWarning(
      response,
      data,
      options?.partialWarning ?? common.partialSuccess,
    ),
  };
}

/** After POST/PATCH/DELETE: throws on failure; surfaces 207 as optional warning text. */
export async function wsMutationResult(
  response: Response,
  fallbackMessage: string,
  partialWarningFallback?: string,
  locale: Locale = 'en',
): Promise<string | null> {
  const partialFallback = partialWarningFallback ?? wsCommonMessages(locale).partialSuccess;
  await throwIfWsNotOk(response, fallbackMessage);
  if (response.status !== 207) {
    return null;
  }
  const data = await response.json().catch(() => ({}));
  return wsPartialSuccessWarning(response, data, partialFallback);
}
