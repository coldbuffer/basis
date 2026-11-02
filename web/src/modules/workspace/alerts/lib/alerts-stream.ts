import { fmt } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { localeFromBrowser } from '@/i18n/locale.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import { basisSessionFetch } from '@/lib/session/basis-session-fetch.js';
import { workspaceApiPath } from '@/lib/workspace/api-path.js';

function resolveLocale(locale?: Locale): Locale {
  if (locale) {
    return locale;
  }
  const lang = typeof navigator !== 'undefined' ? navigator.language : 'en';
  return localeFromBrowser(lang);
}

export type WorkspaceAlertStreamItem = {
  id: string;
  kind: string;
  severity: string;
  message: string;
  detail: Record<string, unknown>;
  created_at: string;
  read_at?: string | null;
  dismissed_at?: string | null;
};

type StreamEvent =
  | { type: 'ready'; workspace_id: string }
  | { type: 'alert'; alert: WorkspaceAlertStreamItem };

function parseSseBlock(block: string): StreamEvent | null {
  const line = block.split('\n').find((l) => l.startsWith('data:'));
  if (!line) return null;
  const raw = line.slice(5).trim();
  if (!raw) return null;
  return JSON.parse(raw) as StreamEvent;
}

/** Authenticated GET SSE for workspace alerts; calls `onAlert` for each new episode. */
export async function consumeWorkspaceAlertsStream(
  workspaceId: string,
  options: {
    since?: string | null;
    signal: AbortSignal;
    onAlert: (alert: WorkspaceAlertStreamItem) => void;
    locale?: Locale;
  },
): Promise<void> {
  const locale = resolveLocale(options.locale);
  const alertsCopy = messagesForLocale(locale).alerts.page;
  const qs = options.since ? `?since=${encodeURIComponent(options.since)}` : '';
  const response = await basisSessionFetch(`${workspaceApiPath(workspaceId, 'alerts/stream')}${qs}`, {
    method: 'GET',
    headers: { Accept: 'text/event-stream' },
    signal: options.signal,
  });
  if (!response.ok) {
    throw new Error(fmt(alertsCopy.stream_failed, { status: response.status }));
  }
  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error(alertsCopy.stream_no_body);
  }
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let split = buffer.indexOf('\n\n');
    while (split !== -1) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      const evt = parseSseBlock(block);
      if (evt?.type === 'alert' && evt.alert) {
        options.onAlert(evt.alert);
      }
      split = buffer.indexOf('\n\n');
    }
  }
}
