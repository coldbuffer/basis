import type { ActivityLogRow } from '@/modules/activity-log/lib/rows.js';
import type { AuditEvent, EntityMergeRow } from '@/modules/activity-log/lib/timeline.js';
import { decisionIdFromDetail } from '@/modules/review/lib/review-url-state.js';

/** Explorer graph governance node ids (excludes legacy agent `dec_*` ids). */
export function isExplorerGraphDecisionId(id: string): boolean {
  const trimmed = id.trim();
  return Boolean(trimmed) && !trimmed.startsWith('dec_');
}

function graphIdFromRecord(detail: Record<string, unknown>): string | null {
  const direct = decisionIdFromDetail(detail);
  if (direct && isExplorerGraphDecisionId(direct)) return direct;

  const graphDecisionId = detail.graph_decision_id;
  if (typeof graphDecisionId === 'string' && isExplorerGraphDecisionId(graphDecisionId)) {
    return graphDecisionId.trim();
  }

  const trace = detail.trace;
  if (trace && typeof trace === 'object' && !Array.isArray(trace)) {
    const fromTrace = (trace as Record<string, unknown>).graph_decision_id;
    if (typeof fromTrace === 'string' && isExplorerGraphDecisionId(fromTrace)) {
      return fromTrace.trim();
    }
  }

  const merge = detail.merge;
  if (merge && typeof merge === 'object' && !Array.isArray(merge)) {
    const fromMerge = (merge as Record<string, unknown>).graph_decision_id;
    if (typeof fromMerge === 'string' && isExplorerGraphDecisionId(fromMerge)) {
      return fromMerge.trim();
    }
  }

  return null;
}

export function collectLinkedGraphDecisionIds(
  events: AuditEvent[],
  merges: EntityMergeRow[],
): Set<string> {
  const ids = new Set<string>();
  for (const event of events) {
    const detail = event.detail;
    if (!detail || typeof detail !== 'object' || Array.isArray(detail)) continue;
    const id = graphIdFromRecord(detail as Record<string, unknown>);
    if (id) ids.add(id);
  }
  for (const merge of merges) {
    const id = merge.decision_id;
    if (id && isExplorerGraphDecisionId(id)) ids.add(id.trim());
  }
  return ids;
}

export function graphDecisionIdFromActivityRow(row: ActivityLogRow): string | null {
  if (row.kind === 'graph_decision') {
    return row.decision.decision_id?.trim() || null;
  }
  if (row.kind === 'ledger_merge') {
    const id = row.merge.decision_id;
    if (id && isExplorerGraphDecisionId(id)) return id.trim();
    return null;
  }
  const detail = row.event.detail;
  if (!detail || typeof detail !== 'object' || Array.isArray(detail)) return null;
  return graphIdFromRecord(detail as Record<string, unknown>);
}
