import type { LocaleMessages } from '@/i18n/en.js';
import { shortenOpaqueId } from '@/lib/workspace/shorten-opaque-id.js';
import {
  formatGraphAuditAction,
  formatGraphAuditDetail,
  reviewItemIdFromGraphAuditDetail,
  type GraphAuditEvent,
} from '@/modules/graph/lib/graph-audit.js';
import type { AuditEvent } from '@/modules/activity-log/lib/timeline.js';
import {
  reviewItemSummaryLine,
  reviewKindLabel,
  type ReviewItemSummaryInput,
} from '@/modules/review/lib/review-item-summary.js';
import type { Locale } from '@/i18n/locale.js';
import { fmt } from '@/i18n/format.js';

export type WorkspaceMemberRow = {
  user_id: string;
  email: string;
  display_name: string;
};

export function collectReviewItemIdsFromAuditEvents(events: AuditEvent[]): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const event of events) {
    const id = reviewItemIdFromGraphAuditDetail(event.detail);
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
  }
  return ids;
}

export function formatAuditActorLabel(
  actorId: string | null | undefined,
  membersByUserId: Map<string, WorkspaceMemberRow>,
  emptyCell: string,
  systemActorLabel: string,
): string {
  if (!actorId?.trim()) return systemActorLabel || emptyCell;
  const member = membersByUserId.get(actorId.trim());
  if (member) {
    const name = member.display_name?.trim();
    if (name) return name;
    const email = member.email?.trim();
    if (email) return email;
  }
  return shortenOpaqueId(actorId);
}

export function auditReviewItemSummaryLine(
  event: AuditEvent,
  reviewItemsById: Map<string, ReviewItemSummaryInput>,
  copy: LocaleMessages['review']['queue'],
  activityLog: LocaleMessages['activity_log']['page'],
  locale: Locale,
  labels: Record<string, string | null | undefined>,
  emptyCell: string,
): string | null {
  const itemId = reviewItemIdFromGraphAuditDetail(event.detail);
  if (!itemId) return null;
  const item = reviewItemsById.get(itemId);
  if (item) {
    const body = reviewItemSummaryLine(item, copy, locale, labels, emptyCell);
    const kind = reviewKindLabel(item.kind, copy);
    return body ? `${kind} · ${body}` : kind;
  }
  return fmt(activityLog.review_item_unresolved, {
    shortId: shortenOpaqueId(itemId),
  });
}

export function activityLogAuditSummaryLine(
  event: AuditEvent & { actor_id?: string | null },
  options: {
    locale: Locale;
    reviewItemsById: Map<string, ReviewItemSummaryInput>;
    reviewCopy: LocaleMessages['review']['queue'];
    activityLogCopy: LocaleMessages['activity_log']['page'];
    labels: Record<string, string | null | undefined>;
    emptyCell: string;
    auditDetailLine: string | null;
  },
): string {
  const {
    locale,
    reviewItemsById,
    reviewCopy,
    activityLogCopy,
    labels,
    emptyCell,
    auditDetailLine,
  } = options;

  const fromReview = auditReviewItemSummaryLine(
    event,
    reviewItemsById,
    reviewCopy,
    activityLogCopy,
    locale,
    labels,
    emptyCell,
  );
  if (fromReview) return fromReview;

  const graphEvent: GraphAuditEvent = {
    id: event.id,
    action: event.action,
    actor_id: event.actor_id ?? null,
    created_at: event.created_at,
    detail: event.detail,
  };
  const fromGraphDetail = formatGraphAuditDetail(graphEvent, locale);
  if (fromGraphDetail) return fromGraphDetail;

  if (auditDetailLine) return auditDetailLine;

  const rationale = event.detail?.rationale;
  if (typeof rationale === 'string' && rationale.trim()) return rationale.trim();

  const actionLabel = formatGraphAuditAction(event.action, locale);
  return actionLabel || emptyCell;
}
