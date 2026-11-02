import type { GraphDiffMergePick } from '@/modules/workspace/graph/lib/diff/graph-diff-merge-pick.js';

const STORAGE_PREFIX = 'basis.graphStagingDraft.';

export function graphStagingDraftStorageKey(sessionKey: string): string {
  return `${STORAGE_PREFIX}${sessionKey.trim()}`;
}

export function readGraphStagingDraft(sessionKey: string): GraphDiffMergePick | null {
  const key = sessionKey.trim();
  if (!key || typeof sessionStorage === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(graphStagingDraftStorageKey(key));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<GraphDiffMergePick>;
    if (typeof parsed !== 'object' || parsed === null) return null;
    return {
      primary: typeof parsed.primary === 'string' ? parsed.primary : '',
      duplicate: typeof parsed.duplicate === 'string' ? parsed.duplicate : '',
    };
  } catch {
    return null;
  }
}

export function writeGraphStagingDraft(sessionKey: string, pick: GraphDiffMergePick): void {
  const key = sessionKey.trim();
  if (!key || typeof sessionStorage === 'undefined') return;
  const primary = pick.primary.trim();
  const duplicate = pick.duplicate.trim();
  if (!primary && !duplicate) {
    sessionStorage.removeItem(graphStagingDraftStorageKey(key));
    return;
  }
  sessionStorage.setItem(
    graphStagingDraftStorageKey(key),
    JSON.stringify({ primary, duplicate }),
  );
}

export function clearGraphStagingDraft(sessionKey: string): void {
  const key = sessionKey.trim();
  if (!key || typeof sessionStorage === 'undefined') return;
  sessionStorage.removeItem(graphStagingDraftStorageKey(key));
}
