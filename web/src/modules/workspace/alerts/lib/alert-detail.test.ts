import { describe, expect, it } from 'vitest';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import {
  alertEpisodeKey,
  groupAlertsByEpisode,
  alertDetailLines,
} from '@/modules/workspace/alerts/lib/alert-detail.js';
import type { WorkspaceAlertStreamItem } from '@/modules/workspace/alerts/lib/alerts-stream.js';

function alert(partial: Partial<WorkspaceAlertStreamItem> & Pick<WorkspaceAlertStreamItem, 'kind'>): WorkspaceAlertStreamItem {
  return {
    id: 'a1',
    severity: 'warning',
    message: 'msg',
    detail: {},
    created_at: '2030-01-01T00:00:00Z',
    ...partial,
  };
}

describe('alertDetailLines', () => {
  const alerts = messagesForLocale('en').alerts.page;

  it('formats governance.tripped detail', () => {
    const lines = alertDetailLines(
      alerts,
      alert({
        kind: 'governance.tripped',
        detail: { code: 'impact_gate_blocked', decision_id: 'dec-1', shacl_violation_count: 2 },
      }),
    );
    expect(lines.some((l) => l.includes('impact_gate_blocked'))).toBe(true);
    expect(lines.some((l) => l.includes('dec-1'))).toBe(true);
    expect(lines.some((l) => l.includes('2'))).toBe(true);
  });
});

describe('groupAlertsByEpisode', () => {
  it('groups by episode_key when present', () => {
    const groups = groupAlertsByEpisode([
      alert({
        id: '1',
        kind: 'processing.failed',
        detail: { episode_key: 'processing:j1', job_id: 'j1' },
      }),
      alert({
        id: '2',
        kind: 'governance.tripped',
        detail: { episode_key: 'governance:code:x' },
      }),
      alert({
        id: '3',
        kind: 'processing.failed',
        detail: { episode_key: 'processing:j1', job_id: 'j1' },
      }),
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0]?.alerts).toHaveLength(2);
    expect(alertEpisodeKey(alert({ id: 'x', kind: 'k', detail: { episode_key: 'e1' } }))).toBe(
      'e1',
    );
  });
});
