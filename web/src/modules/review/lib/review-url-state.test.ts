import { describe, expect, it } from 'vitest';
import {
  auditEventMatchesReviewItem,
  decisionIdFromApproveResponse,
  decisionIdFromDetail,
  reviewDecisionPath,
  reviewItemPath,
  mergeActivityLogGraphDecisionParam,
  parseActivityLogDecisionUrlState,
  parseReviewUrlState,
} from '@/modules/review/lib/review-url-state.js';

describe('reviewUrlState', () => {
  it('parses review item id', () => {
    const state = parseReviewUrlState('?reviewItem=item-42');
    expect(state.reviewItemId).toBe('item-42');
  });

  it('builds review item path', () => {
    const href = reviewItemPath('kb-1', 'item-42');
    expect(href).toBe('/workspaces/kb-1/review?reviewItem=item-42');
  });

  it('builds decision deep link path', () => {
    expect(reviewDecisionPath('kb-1', 'dec-1')).toBe(
      '/workspaces/kb-1/log?graph_decision=dec-1',
    );
  });

  it('parses activity log decision url state', () => {
    const state = parseActivityLogDecisionUrlState('?graph_decision=dec-9&decisions_q=merge');
    expect(state.graphDecisionId).toBe('dec-9');
    expect(state.decisionsQ).toBe('merge');
  });

  it('merges graph decision param', () => {
    const next = mergeActivityLogGraphDecisionParam('decisions_q=merge', 'dec-2');
    expect(next.get('decisions_q')).toBe('merge');
    expect(next.get('graph_decision')).toBe('dec-2');
  });

  it('extracts decision_id from detail', () => {
    expect(decisionIdFromDetail({ decision_id: 'dec-1' })).toBe('dec-1');
    expect(decisionIdFromDetail({ extra: { decision_id: 'dec-2' } })).toBe('dec-2');
  });

  it('reads decision_id from approve response body', () => {
    expect(decisionIdFromApproveResponse({ item: {}, decision_id: 'dec-3' })).toBe('dec-3');
  });

  it('matches audit rows to review item id', () => {
    expect(auditEventMatchesReviewItem({ item_id: 'ri-1' }, 'ri-1')).toBe(true);
    expect(auditEventMatchesReviewItem({ review_item_id: 'ri-2' }, 'ri-2')).toBe(true);
    expect(auditEventMatchesReviewItem({ item_id: 'other' }, 'ri-1')).toBe(false);
  });
});
