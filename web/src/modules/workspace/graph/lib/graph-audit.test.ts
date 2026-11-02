import { describe, expect, it } from 'vitest';
import {
  workspaceIdFromPlatformAuditEvent,
  proposalIdFromGraphAuditDetail,
  reviewItemIdFromGraphAuditDetail,
} from '@/modules/workspace/graph/lib/graph-audit.js';

describe('graph audit detail ids', () => {
  it('resolves workspace id from platform audit rows', () => {
    expect(
      workspaceIdFromPlatformAuditEvent({
        target_type: 'workspace',
        target_id: 'kb-9',
        detail: {},
      }),
    ).toBe('kb-9');
    expect(
      workspaceIdFromPlatformAuditEvent({
        target_type: 'user',
        target_id: null,
        detail: { workspace_id: 'kb-2' },
      }),
    ).toBe('kb-2');
  });

  it('extracts review item ids', () => {
    expect(reviewItemIdFromGraphAuditDetail({ review_item_id: 'ri-1' })).toBe('ri-1');
    expect(reviewItemIdFromGraphAuditDetail({ item_id: 'ri-2' })).toBe('ri-2');
    expect(
      reviewItemIdFromGraphAuditDetail({ payload: { review_item_id: 'ri-3' } }),
    ).toBe('ri-3');
  });

  it('extracts proposal ids', () => {
    expect(proposalIdFromGraphAuditDetail({ proposal_id: 'p-1' })).toBe('p-1');
    expect(proposalIdFromGraphAuditDetail({ extra: { proposal_id: 'p-2' } })).toBe('p-2');
    expect(proposalIdFromGraphAuditDetail({ payload: { proposal_id: 'p-3' } })).toBe('p-3');
  });
});
