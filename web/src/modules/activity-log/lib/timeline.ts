import type { LocaleMessages } from '@/i18n/en.js';
import type { Locale } from '@/i18n/locale.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import { formatNodeRef } from '@/lib/workspace/format-node-ref.js';
import { auditEventMatchesReviewItem, decisionIdFromDetail } from '@/modules/review/lib/review-url-state.js';

export type AuditEvent = {
  id: number;
  action: string;
  created_at: string;
  detail?: Record<string, unknown>;
};

export type EntityMergeRow = {
  id: string;
  source_entity_id: string;
  target_entity_id: string;
  why: string | null;
  created_at: string;
  reverted_at: string | null;
  decision_id?: string | null;
};

export type TimelineEntry =
  | { kind: 'audit'; id: string; at: string; event: AuditEvent }
  | { kind: 'ledger_merge'; id: string; at: string; merge: EntityMergeRow };

export function auditDetailLine(
  locale: Locale,
  event: AuditEvent,
  r: LocaleMessages['review']['queue'],
  audit: LocaleMessages['graph']['audit'],
  labels: Record<string, string | null>,
): string | null {
  const d = event.detail ?? {};
  if (event.action.includes('merge')) {
    const primary = d.primary_id as string | undefined;
    const dupes = d.duplicate_ids as string[] | undefined;
    if (primary && dupes?.length) {
      return `${formatNodeRef(primary, labels)} ← ${dupes.map((id) => formatNodeRef(id, labels)).join(', ')}`;
    }
    const payload = d.payload as { primary_id?: string; duplicate_ids?: string[] } | undefined;
    if (payload?.primary_id) {
      const dupList = payload.duplicate_ids ?? [];
      return `${formatNodeRef(payload.primary_id, labels)} ← ${dupList.map((id) => formatNodeRef(id, labels)).join(', ')}`;
    }
  }
  if (event.action === 'workspace.graph.import' || event.action === 'workspace.graph.import_proposed') {
    const nodes = d.nodes_imported;
    const edges = d.edges_imported;
    const file = d.filename;
    return [
      file,
      nodes != null ? fmt(r.import_nodes, { count: formatLocaleNumber(locale, Number(nodes)) }) : null,
      edges != null ? fmt(r.import_edges, { count: formatLocaleNumber(locale, Number(edges)) }) : null,
    ]
      .filter(Boolean)
      .join(' · ');
  }
  if (event.action === 'workspace.graph.export') {
    const fmtVal = d.format;
    return fmtVal ? String(fmtVal) : null;
  }
  if (event.action === 'workspace.graph.projection_rebuild') {
    const parts: string[] = [];
    if (d.projection_revision != null) {
      parts.push(
        fmt(audit.projection_revision, {
          revision: formatLocaleNumber(locale, Number(d.projection_revision)),
        }),
      );
    }
    if (d.node_count != null && d.edge_count != null) {
      parts.push(`${d.node_count}/${d.edge_count}`);
    }
    return parts.length ? parts.join(' · ') : null;
  }
  const mergePayload = d.merge as { ledger_notice?: string; ledger_skipped_ids?: string[] } | undefined;
  const ledgerNotice = (d.ledger_notice as string | undefined) ?? mergePayload?.ledger_notice;
  const ledgerSkipped =
    (d.ledger_skipped_ids as string[] | undefined) ?? mergePayload?.ledger_skipped_ids;
  if (event.action === 'workspace.graph.merge_approved' && ledgerNotice === 'graph_only_merge') {
    return r.graph_only_merge_approved;
  }
  if (event.action === 'workspace.graph.merge_approved' && ledgerNotice === 'partial_ledger') {
    const skipped = ledgerSkipped?.join(', ');
    return fmt(r.partial_ledger_skipped, { skipped: skipped ?? '' });
  }
  if (event.action === 'workspace.graph.merge_approved') {
    const ledger = d.ledger_merges as { source_entity_id?: string; target_entity_id?: string }[] | undefined;
    if (ledger?.length) {
      return ledger
        .map(
          (row) =>
            `${formatNodeRef(row.source_entity_id ?? '', labels)} → ${formatNodeRef(row.target_entity_id ?? '', labels)}`,
        )
        .join('; ');
    }
    const merge = d.merge as { ledger_merges?: { source_entity_id: string; target_entity_id: string }[] } | undefined;
    if (merge?.ledger_merges?.length) {
      return merge.ledger_merges
        .map(
          (row) =>
            `${formatNodeRef(row.source_entity_id, labels)} → ${formatNodeRef(row.target_entity_id, labels)}`,
        )
        .join('; ');
    }
  }
  return null;
}

export function collectAuditLabelIds(events: AuditEvent[]): string[] {
  const ids: string[] = [];
  for (const event of events) {
    const d = event.detail ?? {};
    const primary = d.primary_id as string | undefined;
    if (primary) ids.push(primary);
    const dupes = d.duplicate_ids as string[] | undefined;
    if (dupes?.length) ids.push(...dupes);
    const payload = d.payload as { primary_id?: string; duplicate_ids?: string[] } | undefined;
    if (payload?.primary_id) ids.push(payload.primary_id);
    if (payload?.duplicate_ids?.length) ids.push(...payload.duplicate_ids);
    const ledger = d.ledger_merges as { source_entity_id?: string; target_entity_id?: string }[] | undefined;
    for (const row of ledger ?? []) {
      if (row.source_entity_id) ids.push(row.source_entity_id);
      if (row.target_entity_id) ids.push(row.target_entity_id);
    }
    const merge = d.merge as { ledger_merges?: { source_entity_id: string; target_entity_id: string }[] } | undefined;
    for (const row of merge?.ledger_merges ?? []) {
      ids.push(row.source_entity_id, row.target_entity_id);
    }
  }
  return ids;
}

export function mergeTimeline(events: AuditEvent[], merges: EntityMergeRow[]): TimelineEntry[] {
  const rows: TimelineEntry[] = events.map((event) => ({
    kind: 'audit',
    id: `audit-${event.id}`,
    at: event.created_at,
    event,
  }));
  for (const merge of merges) {
    rows.push({
      kind: 'ledger_merge',
      id: `merge-${merge.id}`,
      at: merge.created_at,
      merge,
    });
  }
  return rows.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
}

export function decisionIdsForReviewItem(events: AuditEvent[], itemId: string): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const event of events) {
    if (!auditEventMatchesReviewItem(event.detail, itemId)) continue;
    const decisionId = decisionIdFromDetail(event.detail);
    if (!decisionId || seen.has(decisionId)) continue;
    seen.add(decisionId);
    ids.push(decisionId);
  }
  return ids;
}

export function filterTimelineForReviewItem(entries: TimelineEntry[], itemId: string): TimelineEntry[] {
  return entries.filter((entry) => {
    if (entry.kind !== 'audit') return false;
    return auditEventMatchesReviewItem(entry.event.detail, itemId);
  });
}

export function collectMergeLabelIds(merges: EntityMergeRow[]): string[] {
  const ids: string[] = [];
  for (const row of merges) {
    ids.push(row.source_entity_id, row.target_entity_id);
  }
  return ids;
}
