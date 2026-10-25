import type { AuditEvent, EntityMergeRow } from '@/modules/activity-log/lib/timeline.js';
import type { DecisionRow } from '@/modules/decisions/lib/decision-display.js';
import { collectLinkedGraphDecisionIds } from '@/modules/activity-log/lib/graph-decision-id.js';

export type ActivityLogKindFilter = 'all' | 'audit' | 'ledger_merge' | 'graph_decision';

export type ActivityLogRow =
  | { kind: 'audit'; rowKey: string; at: string; event: AuditEvent & { actor_id?: string | null } }
  | { kind: 'ledger_merge'; rowKey: string; at: string; merge: EntityMergeRow }
  | { kind: 'graph_decision'; rowKey: string; at: string; decision: DecisionRow };

export function buildActivityLogRows(
  events: (AuditEvent & { actor_id?: string | null })[],
  merges: EntityMergeRow[],
  kindFilter: ActivityLogKindFilter,
  graphDecisions: DecisionRow[] = [],
): ActivityLogRow[] {
  const rows: ActivityLogRow[] = [];
  if (kindFilter === 'all' || kindFilter === 'audit') {
    for (const event of events) {
      rows.push({
        kind: 'audit',
        rowKey: `audit-${event.id}`,
        at: event.created_at,
        event,
      });
    }
  }
  if (kindFilter === 'all' || kindFilter === 'ledger_merge') {
    for (const merge of merges) {
      rows.push({
        kind: 'ledger_merge',
        rowKey: `merge-${merge.id}`,
        at: merge.created_at,
        merge,
      });
    }
  }
  if (kindFilter === 'all' && graphDecisions.length > 0) {
    const linked = collectLinkedGraphDecisionIds(events, merges);
    for (const decision of graphDecisions) {
      const id = decision.decision_id?.trim();
      if (!id || linked.has(id)) continue;
      rows.push({
        kind: 'graph_decision',
        rowKey: `decision-${id}`,
        at: decision.timestamp?.trim() || '',
        decision,
      });
    }
  }
  return rows.sort((a, b) => {
    if (!a.at && !b.at) return 0;
    if (!a.at) return 1;
    if (!b.at) return -1;
    return a.at < b.at ? 1 : a.at > b.at ? -1 : 0;
  });
}

export function filterActivityLogRows(
  rows: ActivityLogRow[],
  query: string,
  match: (row: ActivityLogRow) => string,
): ActivityLogRow[] {
  const q = query.trim().toLowerCase();
  if (!q) return rows;
  return rows.filter((row) => match(row).toLowerCase().includes(q));
}
