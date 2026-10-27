import { fmt } from '@/i18n/format.js';
import type { LocaleMessages } from '@/i18n/en.js';
import type { WorkspaceAlertStreamItem } from '@/modules/alerts/lib/alerts-stream.js';

type AlertsCopy = LocaleMessages['alerts']['page'];

function detailString(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return null;
}

/** Secondary lines for alert list rows (F-ALT / F-GOV-05). */
export function alertDetailLines(
  alerts: AlertsCopy,
  alert: WorkspaceAlertStreamItem,
): string[] {
  const d = alert.detail ?? {};
  const lines: string[] = [];

  if (alert.kind === 'governance.tripped') {
    const code = detailString(d.code);
    if (code) lines.push(fmt(alerts.governance_tripped_code, { code }));
    const decisionId = detailString(d.decision_id);
    if (decisionId) lines.push(fmt(alerts.governance_tripped_decision, { id: decisionId }));
    const itemId = detailString(d.item_id);
    if (itemId) lines.push(fmt(alerts.governance_tripped_review_item, { id: itemId }));
    const proposalId = detailString(d.proposal_id);
    if (proposalId) lines.push(fmt(alerts.governance_tripped_proposal, { id: proposalId }));
    const shacl = d.shacl_violation_count ?? d.shacl_count;
    const shaclN = typeof shacl === 'number' ? shacl : Number(shacl);
    if (Number.isFinite(shaclN) && shaclN > 0) {
      lines.push(fmt(alerts.governance_tripped_shacl, { count: shaclN }));
    }
    return lines;
  }

  if (alert.kind === 'processing.failed') {
    const jobId = detailString(d.job_id);
    if (jobId) lines.push(fmt(alerts.processing_failed_job, { id: jobId }));
    const errorCode = detailString(d.error_code);
    if (errorCode) lines.push(fmt(alerts.processing_failed_code, { code: errorCode }));
    return lines;
  }

  if (alert.kind === 'sync_failed') {
    const sourceId = detailString(d.source_id);
    if (sourceId) lines.push(fmt(alerts.sync_failed_source, { id: sourceId }));
    return lines;
  }

  return lines;
}

export function alertEpisodeKey(alert: WorkspaceAlertStreamItem): string {
  const d = alert.detail ?? {};
  const episode = d.episode_key;
  if (typeof episode === 'string' && episode.trim()) return episode.trim();
  return `${alert.kind}:${alert.id}`;
}

/** Group alert rows by `detail.episode_key` (F-ALT), preserving first-seen order. */
export function groupAlertsByEpisode(
  alerts: WorkspaceAlertStreamItem[],
): Array<{ episodeKey: string; kind: string; alerts: WorkspaceAlertStreamItem[] }> {
  const order: string[] = [];
  const map = new Map<string, WorkspaceAlertStreamItem[]>();
  for (const alert of alerts) {
    const key = alertEpisodeKey(alert);
    if (!map.has(key)) {
      map.set(key, []);
      order.push(key);
    }
    map.get(key)!.push(alert);
  }
  return order.map((episodeKey) => {
    const group = map.get(episodeKey)!;
    return { episodeKey, kind: group[0]!.kind, alerts: group };
  });
}
