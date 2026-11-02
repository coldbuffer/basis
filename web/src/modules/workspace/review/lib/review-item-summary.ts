import type { LocaleMessages } from '@/i18n/en.js';
import type { Locale } from '@/i18n/locale.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import { formatNodeRef } from '@/lib/workspace/format-node-ref.js';

export type ReviewItemSummaryInput = {
  id: string;
  kind: string;
  status?: string;
  payload: Record<string, unknown>;
};

export function reviewKindLabel(
  kind: string,
  copy: LocaleMessages['review']['queue'],
): string {
  if (kind === 'graph_import') return copy.kind_import;
  if (kind === 'ontology_mapping') return copy.kind_mapping;
  if (kind === 'statement_remember') return copy.kind_remember;
  if (kind === 'shacl_violation') return copy.kind_shacl;
  if (kind === 'low_confidence') return copy.kind_low_confidence;
  if (kind === 'entity_cluster') return copy.kind_entity_cluster;
  if (kind === 'unmapped_entity_type') return copy.kind_unmapped_entity_type;
  if (kind === 'vocabulary_alignment_change') return copy.kind_vocabulary_alignment_change;
  if (kind === 'connector_writeback') return copy.kind_writeback;
  if (kind === 'entity_merge') return copy.kind_merge;
  return kind;
}

/** One-line summary for governance log / audit (plain text). */
export function reviewItemSummaryLine(
  item: ReviewItemSummaryInput,
  copy: LocaleMessages['review']['queue'],
  locale: Locale,
  labels: Record<string, string | null | undefined>,
  emptyCell: string,
): string {
  const payload = item.payload;
  const kind = item.kind;

  if (kind === 'graph_import') {
    const filename = payload.filename ?? copy.import_default_filename;
    const size =
      payload.byte_size != null
        ? fmt(copy.import_byte_size, {
            size: formatLocaleNumber(locale, Number(payload.byte_size)),
          })
        : '?';
    return `${String(filename)} (${size})`;
  }

  if (kind === 'ontology_mapping') {
    const sig = payload.signature ?? emptyCell;
    const target = payload.target_uri ?? emptyCell;
    const targetKind = payload.target_kind ?? copy.mapping_kind_unknown;
    return `${String(sig)} → ${String(target)} (${String(targetKind)})`;
  }

  if (kind === 'statement_remember') {
    const text = payload.content ?? payload.statement_id ?? emptyCell;
    return String(text).replace(/\s+/g, ' ').trim();
  }

  if (kind === 'low_confidence') {
    return fmt(copy.low_confidence_line, {
      confidence: String(payload.confidence ?? emptyCell),
      threshold: String(payload.confidence_min ?? emptyCell),
      predicate: String(payload.surface_phrase ?? emptyCell),
    });
  }

  if (kind === 'unmapped_entity_type') {
    return fmt(copy.unmapped_entity_type_line, {
      label: String(payload.label ?? emptyCell),
    });
  }

  if (kind === 'vocabulary_alignment_change') {
    const action = String(payload.action ?? 'change');
    const alignment =
      payload.action === 'delete' && payload.alignment && typeof payload.alignment === 'object'
        ? (payload.alignment as Record<string, unknown>)
        : payload;
    return fmt(copy.vocabulary_alignment_line, {
      action,
      source: String(alignment.source_uri ?? emptyCell),
      target: String(alignment.target_uri ?? emptyCell),
      relation: String(alignment.relation ?? emptyCell),
    });
  }

  if (kind === 'entity_cluster') {
    const source = String(payload.source ?? '');
    if (source === 'graph_semantic_dedup') {
      return fmt(copy.entity_cluster_semantic_line, {
        similarity: String(payload.similarity ?? emptyCell),
        count: formatLocaleNumber(locale, (payload.entity_ids as string[] | undefined)?.length ?? 0),
      });
    }
    return fmt(copy.entity_cluster_line, {
      label: String(payload.canonical_label ?? emptyCell),
      count: formatLocaleNumber(locale, (payload.entity_ids as string[] | undefined)?.length ?? 0),
    });
  }

  if (kind === 'shacl_violation') {
    const message = String((payload as { message?: string }).message ?? emptyCell);
    const subject = payload.subject_id
      ? formatNodeRef(String(payload.subject_id), labels)
      : null;
    return subject ? `${subject} · ${message}` : message;
  }

  if (kind === 'connector_writeback') {
    const provider = payload.provider ?? emptyCell;
    const table = payload.external_table ?? emptyCell;
    const pk = payload.external_pk ?? emptyCell;
    return `${String(provider)} · ${String(table)} (${String(pk)})`;
  }

  if (kind === 'entity_merge') {
    const primary = payload.primary_id ? formatNodeRef(String(payload.primary_id), labels) : emptyCell;
    const dupes = (payload.duplicate_ids as string[] | undefined) ?? [];
    const dupPart = dupes.map((id) => formatNodeRef(id, labels)).join(', ');
    return dupPart ? `${primary} ← ${dupPart}` : String(primary);
  }

  return reviewKindLabel(kind, copy);
}

export function collectReviewItemLabelIds(items: Iterable<ReviewItemSummaryInput>): string[] {
  const ids: string[] = [];
  for (const item of items) {
    const payload = item.payload;
    if (item.kind === 'entity_merge') {
      if (payload.primary_id) ids.push(String(payload.primary_id));
      for (const id of (payload.duplicate_ids as string[] | undefined) ?? []) ids.push(id);
    }
    if (item.kind === 'shacl_violation') {
      if (payload.subject_id) ids.push(String(payload.subject_id));
      for (const obj of (payload.objects as { object_entity_id?: string }[] | undefined) ?? []) {
        if (obj.object_entity_id) ids.push(obj.object_entity_id);
      }
    }
    if (item.kind === 'entity_cluster') {
      for (const id of (payload.entity_ids as string[] | undefined) ?? []) ids.push(id);
      if (payload.suggested_primary_id) ids.push(String(payload.suggested_primary_id));
    }
  }
  return ids;
}
