import type { LocaleMessages } from '@/i18n/en.js';
import { decisionCategoryLabel } from '@/modules/decisions/i18n/screen-copy.js';

export type DecisionRow = {
  decision_id: string;
  category?: string;
  scenario?: string;
  reasoning?: string;
  outcome?: string;
  confidence?: number;
  timestamp?: string | null;
  metadata?: Record<string, unknown>;
};

const REASONING_PREVIEW_MAX = 120;

export function decisionListTitle(
  row: DecisionRow,
  copy: LocaleMessages['decisions']['page'],
): string {
  const summary = row.metadata?.summary;
  if (typeof summary === 'string' && summary.trim()) return summary.trim();
  const scenario = row.scenario?.trim();
  if (scenario) return scenario;
  const fromReasoning = reasoningPlainLine(row.reasoning);
  if (fromReasoning) return fromReasoning;
  if (row.category) return decisionCategoryLabel(copy, row.category);
  return copy.list_untitled;
}

export function decisionListPreview(row: DecisionRow): string {
  const scenario = row.scenario?.trim();
  const line = reasoningPlainLine(row.reasoning);
  if (scenario && line && line !== scenario) {
    return line.length > REASONING_PREVIEW_MAX ? `${line.slice(0, REASONING_PREVIEW_MAX)}…` : line;
  }
  return '';
}

function reasoningPlainLine(reasoning?: string): string {
  const raw = reasoning?.trim();
  if (!raw) return '';
  if (raw.startsWith('{')) {
    try {
      const obj = JSON.parse(raw) as Record<string, unknown>;
      const msg = obj.message ?? obj.rationale ?? obj.summary;
      if (typeof msg === 'string' && msg.trim()) return msg.trim();
      const code = obj.code;
      if (typeof code === 'string' && code.trim()) return code.trim();
    } catch {
      /* fall through */
    }
  }
  const firstLine = raw.split('\n')[0]?.trim() ?? raw;
  return firstLine.length > 200 ? `${firstLine.slice(0, 200)}…` : firstLine;
}

export function formatDecisionReasoningBody(reasoning?: string): string {
  const raw = reasoning?.trim();
  if (!raw) return '';
  if (raw.startsWith('{')) {
    try {
      const obj = JSON.parse(raw) as Record<string, unknown>;
      const lines: string[] = [];
      const preferred = [
        'summary',
        'message',
        'primary_label',
        'duplicate_labels',
        'code',
        'kind',
        'review_item_id',
        'statement_id',
        'workspace_id',
        'alert_kind',
        'cluster_source',
      ];
      for (const key of preferred) {
        const val = obj[key];
        if (val === undefined || val === null) continue;
        if (key === 'duplicate_labels' && typeof val === 'object' && !Array.isArray(val)) {
          const pairs = Object.entries(val as Record<string, unknown>)
            .map(([id, lab]) => `${String(lab)} (${id})`)
            .join('；');
          if (pairs) lines.push(`duplicate_labels: ${pairs}`);
          continue;
        }
        const text = typeof val === 'object' ? JSON.stringify(val) : String(val);
        if (text.trim()) lines.push(`${key}: ${text}`);
      }
      const rest = Object.keys(obj).filter((k) => !preferred.includes(k));
      for (const key of rest.sort()) {
        const val = obj[key];
        if (val === undefined || val === null) continue;
        const text = typeof val === 'object' ? JSON.stringify(val) : String(val);
        if (text.trim()) lines.push(`${key}: ${text}`);
      }
      return lines.join('\n');
    } catch {
      return raw;
    }
  }
  return raw;
}

export function reviewItemIdFromDecision(row: DecisionRow): string | null {
  const meta = row.metadata;
  const fromMeta = meta?.review_item_id ?? meta?.reviewItemId;
  if (typeof fromMeta === 'string' && fromMeta.trim()) return fromMeta.trim();
  const raw = row.reasoning?.trim();
  if (!raw?.startsWith('{')) return null;
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>;
    const id = obj.review_item_id ?? obj.reviewItemId;
    return typeof id === 'string' && id.trim() ? id.trim() : null;
  } catch {
    return null;
  }
}
