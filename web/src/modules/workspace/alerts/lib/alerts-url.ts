import { workspacePath } from '@/lib/nav/nav-config.js';

const EPISODE_PARAM = 'episode';

/** Matches `emit_processing_failed_alert` episode keys (F-ALT). */
export function processingAlertEpisodeKey(jobId: string): string {
  return `processing:${jobId.trim()}`;
}

/** Review-queue deep links for governance alerts. */
export function reviewAlertEpisodeKey(reviewItemId: string): string {
  return `review:${reviewItemId.trim()}`;
}

export function parseKbAlertsUrlState(search: string): { episodeKey?: string } {
  const episode = new URLSearchParams(search).get(EPISODE_PARAM)?.trim();
  return episode ? { episodeKey: episode } : {};
}

export function workspaceAlertsPath(workspaceId: string, opts?: { episodeKey?: string }): string {
  const base = workspacePath(workspaceId, 'alerts');
  const episode = opts?.episodeKey?.trim();
  if (!episode) return base;
  const params = new URLSearchParams();
  params.set(EPISODE_PARAM, episode);
  return `${base}?${params.toString()}`;
}
