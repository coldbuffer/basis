import type { WorkspaceHttpConfig } from '@/lib/workspace/ws-http.js';
import { fmt } from '@/i18n/format.js';
import { localeFromBrowser, type Locale } from '@/i18n/locale.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import { getToken } from '@/lib/session/auth-token.js';
import type { ApiErrorWithMeta } from '@/lib/errors/api-error.js';
import { errorFromApiResponse } from '@/lib/errors/api-error.js';
import { workspaceApiRoot } from '@/lib/workspace/api-path.js';
import { workspaceOpenApiPOST } from '@/lib/openapi/client.js';
import { realtimeWsOrigin } from '@/lib/workspace/realtime-ws-origin.js';

function resolveLocale(locale?: Locale): Locale {
  if (locale) {
    return locale;
  }
  const lang = typeof navigator !== 'undefined' ? navigator.language : 'en';
  return localeFromBrowser(lang);
}

export function buildWorkspaceHttpConfig(workspaceId: string, locale?: Locale): WorkspaceHttpConfig {
  const loc = resolveLocale(locale);
  return {
    apiRoot: workspaceApiRoot(workspaceId),
    getAuthHeaders: (): Record<string, string> => {
      const token = getToken();
      if (!token) return {};
      return { Authorization: `Bearer ${token}` };
    },
    openGraphUpdatesSocket: async () => {
      try {
        const body = await workspaceOpenApiPOST<{ ticket: string }>(workspaceId, 'realtime-ticket');
        const url = `${realtimeWsOrigin()}${workspaceApiRoot(workspaceId)}/ws/graph-updates?ticket=${encodeURIComponent(body.ticket)}`;
        return new WebSocket(url);
      } catch (err) {
        const apiErr = err as ApiErrorWithMeta;
        if (typeof apiErr.status === 'number') {
          throw errorFromApiResponse(
            apiErr.status,
            { detail: { message: apiErr.message, code: apiErr.code } },
            fmt(messagesForLocale(loc).core.workspace_runtime.realtime_ticket_failed, {
              status: apiErr.status,
            }),
            loc,
          );
        }
        throw err;
      }
    },
  };
}
