import { fmt } from '@/i18n/format.js';
import type { LocaleMessages } from '@/i18n/en.js';

export type DocumentTimelineEvent = {
  kind: string;
  at?: string | null;
  version_id?: string;
  status?: string;
  job_id?: string;
  error_code?: string | null;
  statement_id?: string;
  surface_phrase?: string;
  invalidated_at?: string | null;
  mention_id?: string;
  text?: string;
  byte_size?: number;
};

export type DocumentTimelineResponse = {
  document_id: string;
  doc_id?: string | null;
  events: DocumentTimelineEvent[];
};

/** ISO instants from timeline events, ascending. */
export function documentTimelineInstants(events: DocumentTimelineEvent[]): string[] {
  const seen = new Set<string>();
  const instants: string[] = [];
  for (const event of events) {
    const at = event.at?.trim();
    if (!at || seen.has(at)) continue;
    seen.add(at);
    instants.push(at);
  }
  return instants.sort();
}

/** Suggested graph-diff range from first/last event instants (F-TIM-02 → F-DIFF-01). */
export function documentTimelineDiffRange(events: DocumentTimelineEvent[]): {
  from?: string;
  to?: string;
} {
  const instants = documentTimelineInstants(events);
  if (instants.length === 0) return {};
  if (instants.length === 1) return { to: instants[0] };
  return { from: instants[0], to: instants[instants.length - 1] };
}

export function documentTimelineEventLine(
  copy: LocaleMessages['library']['sources']['timeline'],
  event: DocumentTimelineEvent,
): string {
  const kind = event.kind as keyof typeof copy.kind;
  const label = kind in copy.kind ? copy.kind[kind] : event.kind;
  switch (event.kind) {
    case 'version_created':
      return fmt(copy.version_created, {
        label,
        status: event.status ?? '—',
      });
    case 'processing_job': {
      const base = fmt(copy.processing_job, {
        label,
        status: event.status ?? '—',
      });
      const code = event.error_code?.trim();
      return code ? `${base}${fmt(copy.processing_job_code, { code })}` : base;
    }
    case 'statement_recorded':
      return fmt(copy.statement_recorded, {
        label,
        phrase: event.surface_phrase ?? '—',
      });
    case 'time_mention':
      return fmt(copy.time_mention, {
        label,
        text: event.text ?? '—',
      });
    default:
      return label;
  }
}
