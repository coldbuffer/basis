import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';

export type GraphAuditEvent = {
  id: number;
  action: string;
  actor_id: string | null;
  created_at: string;
  detail?: Record<string, unknown>;
};

export function formatGraphAuditAction(action: string, locale: Locale): string {
  const m = messagesForLocale(locale);
  const actions = {
    ...m.admin_audit.actions,
    ...m.graph.audit.actions,
  } as Record<string, string>;
  const label = actions[action];
  if (label) return label;
  if (!action.trim()) return '';
  const parts = action.split('.').filter(Boolean);
  const tail = parts.slice(-2).join(' ') || action;
  return tail.replace(/_/g, ' ');
}

const NO_GRAPH_AUDIT_DETAIL_LINE = '';

/** Returns a detail line, or `''` when this formatter has nothing to add (not the UI empty cell). */
export function formatGraphAuditDetail(event: GraphAuditEvent, locale: Locale): string {
  const messages = messagesForLocale(locale);
  const copy = messages.graph.audit;
  const d = event.detail ?? {};
  if (event.action === 'workspace.graph.projection_rebuild') {
    const parts: string[] = [];
    if (d.projection_revision != null) {
      parts.push(
        fmt(copy.projection_revision, {
          revision: formatLocaleNumber(locale, Number(d.projection_revision)),
        }),
      );
    }
    if (d.node_count != null && d.edge_count != null) {
      parts.push(
        fmt(copy.nodes_edges_ratio, {
          nodes: formatLocaleNumber(locale, Number(d.node_count)),
          edges: formatLocaleNumber(locale, Number(d.edge_count)),
        }),
      );
    }
    return parts.length > 0 ? parts.join(' · ') : NO_GRAPH_AUDIT_DETAIL_LINE;
  }
  if (event.action === 'workspace.graph.export' && d.format) {
    return String(d.format);
  }
  if (
    (event.action === 'workspace.graph.import' || event.action === 'workspace.graph.import_proposed') &&
    (d.filename != null || d.nodes_imported != null)
  ) {
    return [
      d.filename,
      d.nodes_imported != null
        ? fmt(copy.nodes_imported, { count: formatLocaleNumber(locale, Number(d.nodes_imported)) })
        : null,
      d.edges_imported != null
        ? fmt(copy.edges_imported, { count: formatLocaleNumber(locale, Number(d.edges_imported)) })
        : null,
    ]
      .filter(Boolean)
      .join(' · ');
  }
  return NO_GRAPH_AUDIT_DETAIL_LINE;
}

export function proposalIdFromGraphAuditDetail(
  detail: Record<string, unknown> | undefined,
): string | null {
  if (!detail) return null;
  const direct = detail.proposal_id;
  if (typeof direct === 'string' && direct.trim()) return direct.trim();
  const extra = detail.extra;
  if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
    const nested = (extra as Record<string, unknown>).proposal_id;
    if (typeof nested === 'string' && nested.trim()) return nested.trim();
  }
  const payload = detail.payload;
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    const nested = (payload as Record<string, unknown>).proposal_id;
    if (typeof nested === 'string' && nested.trim()) return nested.trim();
  }
  return null;
}

export function workspaceIdFromAuditDetail(detail: Record<string, unknown> | undefined): string | null {
  if (!detail) return null;
  const workspaceId = detail.workspace_id;
  if (typeof workspaceId === 'string' && workspaceId.trim()) return workspaceId.trim();
  return null;
}

/** Resolve workspace scope for platform audit rows (graph registry deep links). */
export function workspaceIdFromPlatformAuditEvent(event: {
  target_type: string;
  target_id: string | null;
  detail?: Record<string, unknown>;
}): string | null {
  return workspaceIdFromAuditDetail(event.detail) ?? (event.target_type === 'workspace' && event.target_id
    ? event.target_id
    : null);
}

export function reviewItemIdFromGraphAuditDetail(
  detail: Record<string, unknown> | undefined,
): string | null {
  if (!detail) return null;
  for (const key of ['review_item_id', 'item_id'] as const) {
    const v = detail[key];
    if (typeof v === 'string' && v.trim()) return v.trim();
  }
  const payload = detail.payload;
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    const nested = (payload as Record<string, unknown>).review_item_id;
    if (typeof nested === 'string' && nested.trim()) return nested.trim();
  }
  return null;
}
