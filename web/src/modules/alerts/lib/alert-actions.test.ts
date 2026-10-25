import { describe, expect, it } from 'vitest';
import { workspaceAlertAction } from '@/modules/alerts/lib/alert-actions.js';
import type { WorkspaceAlertStreamItem } from '@/modules/alerts/lib/alerts-stream.js';

function alert(partial: Partial<WorkspaceAlertStreamItem> & Pick<WorkspaceAlertStreamItem, 'kind'>): WorkspaceAlertStreamItem {
  return {
    id: 'a1',
    severity: 'warning',
    message: 'test',
    detail: {},
    created_at: '2026-01-01T00:00:00Z',
    ...partial,
  };
}

describe('workspaceAlertAction', () => {
  it('links ontology proposals', () => {
    const action = workspaceAlertAction(
      'kb-1',
      alert({
        kind: 'governance.proposal_proposed',
        detail: { proposal_id: 'prop-9' },
      }),
    );
    expect(action?.href).toContain('/workspaces/kb-1/ontology?tab=versions');
    expect(action?.href).toContain('ontologyProposal=prop-9');
    expect(action?.labelKey).toBe('viewProposal');
  });

  it('links governance tripped with proposal to ontology', () => {
    const action = workspaceAlertAction(
      'kb-1',
      alert({ kind: 'governance.tripped', detail: { proposal_id: 'p2' } }),
    );
    expect(action?.labelKey).toBe('viewProposal');
  });

  it('links governance tripped with decision id to decisions tab', () => {
    const action = workspaceAlertAction(
      'kb-1',
      alert({ kind: 'governance.tripped', detail: { decision_id: 'dec-9' } }),
    );
    expect(action?.href).toBe('/workspaces/kb-1/log?graph_decision=dec-9');
    expect(action?.labelKey).toBe('viewDecisions');
  });

  it('links governance tripped with review item to queue deep link', () => {
    const action = workspaceAlertAction(
      'kb-1',
      alert({ kind: 'governance.tripped', detail: { item_id: 'item-3' } }),
    );
    expect(action?.href).toBe('/workspaces/kb-1/review?reviewItem=item-3');
    expect(action?.labelKey).toBe('viewReview');
  });

  it('links processing.failed to job history deep link', () => {
    const action = workspaceAlertAction(
      'kb-1',
      alert({ kind: 'processing.failed', detail: { job_id: 'job-42' } }),
    );
    expect(action?.href).toBe('/workspaces/kb-1/processing?job=job-42');
    expect(action?.labelKey).toBe('viewProcessingJob');
  });

  it('links sync_failed to sources page', () => {
    const action = workspaceAlertAction('kb-1', alert({ kind: 'sync_failed', detail: { source_id: 's1' } }));
    expect(action?.href).toBe('/workspaces/kb-1/sources');
  });

  it('links llm alerts to workspace settings', () => {
    const action = workspaceAlertAction('kb-1', alert({ kind: 'llm.tool_loop_limit' }));
    expect(action?.href).toBe('/workspaces/kb-1/settings');
    expect(action?.labelKey).toBe('viewSettings');
  });
});
