import { workspaceLogPath, workspaceReviewPath } from '@/lib/nav/nav-config.js';

/** Sole owner of review queue deep-link query params. */
const ITEM_PARAM = 'reviewItem';

export function parseReviewUrlState(search: string): { reviewItemId?: string } {
  const params = new URLSearchParams(search);
  return {
    reviewItemId: params.get(ITEM_PARAM) ?? undefined,
  };
}

/** Deep-link to the review queue with a specific item in view (F-GOV / F-ALT). */
export function reviewItemPath(workspaceId: string, itemId: string): string {
  const params = new URLSearchParams({ [ITEM_PARAM]: itemId });
  return `${workspaceReviewPath(workspaceId)}?${params.toString()}`;
}

export const GRAPH_DECISION_PARAM = 'graph_decision';
export const DECISIONS_BROWSE_PARAM = 'decisions_browse';
export const DECISIONS_Q_PARAM = 'decisions_q';

/** Deep-link to governance log with graph decision detail open (F-GOV-07). */
export function reviewDecisionPath(workspaceId: string, decisionId: string): string {
  const params = new URLSearchParams({ [GRAPH_DECISION_PARAM]: decisionId });
  return `${workspaceLogPath(workspaceId)}?${params.toString()}`;
}

/** Open the full graph-decisions catalog on the change log. */
export function activityLogBrowseDecisionsPath(
  workspaceId: string,
  options?: { q?: string },
): string {
  const params = new URLSearchParams({ [DECISIONS_BROWSE_PARAM]: '1' });
  const q = options?.q?.trim();
  if (q) params.set(DECISIONS_Q_PARAM, q);
  return `${workspaceLogPath(workspaceId)}?${params.toString()}`;
}

export function parseActivityLogDecisionUrlState(search: string): {
  graphDecisionId?: string;
  decisionsQ?: string;
  openBrowse?: boolean;
} {
  const params = new URLSearchParams(search);
  const graphDecisionId = params.get(GRAPH_DECISION_PARAM) ?? undefined;
  const decisionsQ = params.get(DECISIONS_Q_PARAM) ?? undefined;
  const openBrowse = params.get(DECISIONS_BROWSE_PARAM) === '1';
  return {
    graphDecisionId: graphDecisionId?.trim() || undefined,
    decisionsQ: decisionsQ?.trim() || undefined,
    openBrowse,
  };
}

/** Sync governance log `?graph_decision=` while preserving other query params. */
export function mergeActivityLogGraphDecisionParam(
  search: string,
  decisionId: string | null | undefined,
): URLSearchParams {
  const params = new URLSearchParams(search);
  const trimmed = decisionId?.trim();
  if (trimmed) params.set(GRAPH_DECISION_PARAM, trimmed);
  else params.delete(GRAPH_DECISION_PARAM);
  return params;
}

/** Extract Explorer governance decision id from audit/alert detail blobs. */
export function decisionIdFromApproveResponse(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null;
  return decisionIdFromDetail(body as Record<string, unknown>);
}

/** True when a graph audit row belongs to a review queue item (deep-link filter). */
export function auditEventMatchesReviewItem(
  detail: Record<string, unknown> | undefined,
  itemId: string,
): boolean {
  if (!detail || !itemId.trim()) return false;
  const id = itemId.trim();
  const direct = detail.item_id;
  if (typeof direct === 'string' && direct.trim() === id) return true;
  const reviewItemId = detail.review_item_id;
  if (typeof reviewItemId === 'string' && reviewItemId.trim() === id) return true;
  const payload = detail.payload;
  if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
    const nested = (payload as Record<string, unknown>).review_item_id;
    if (typeof nested === 'string' && nested.trim() === id) return true;
  }
  return false;
}

export function decisionIdFromDetail(detail: Record<string, unknown> | undefined): string | null {
  if (!detail) return null;
  const direct = detail.decision_id;
  if (typeof direct === 'string' && direct.trim()) return direct.trim();
  const extra = detail.extra;
  if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
    const nested = (extra as Record<string, unknown>).decision_id;
    if (typeof nested === 'string' && nested.trim()) return nested.trim();
  }
  return null;
}
