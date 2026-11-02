import { describe, expect, it } from 'vitest';
import {
  workspaceAlertsPath,
  parseKbAlertsUrlState,
  processingAlertEpisodeKey,
} from '@/modules/workspace/alerts/lib/alerts-url.js';

describe('workspace-alerts-url', () => {
  it('builds episode deep links', () => {
    expect(processingAlertEpisodeKey('job-1')).toBe('processing:job-1');
    expect(workspaceAlertsPath('kb-1', { episodeKey: 'processing:job-1' })).toBe(
      '/workspaces/kb-1/alerts?episode=processing%3Ajob-1',
    );
    expect(parseKbAlertsUrlState('?episode=processing%3Aj').episodeKey).toBe('processing:j');
  });
});
