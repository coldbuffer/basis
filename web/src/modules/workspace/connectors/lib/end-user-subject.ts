const STORAGE_KEY = 'basis_integration_playground_subject';

export function readEndUserSubjectId(workspaceId: string): string {
  if (typeof window === 'undefined') {
    return defaultEndUserSubjectId(workspaceId);
  }
  try {
    const raw = sessionStorage.getItem(`${STORAGE_KEY}:${workspaceId}`);
    if (raw?.trim()) {
      return raw.trim();
    }
  } catch {
    /* ignore */
  }
  return defaultEndUserSubjectId(workspaceId);
}

export function writeEndUserSubjectId(workspaceId: string, subjectId: string): void {
  try {
    sessionStorage.setItem(`${STORAGE_KEY}:${workspaceId}`, subjectId.trim());
  } catch {
    /* ignore */
  }
}

export function defaultEndUserSubjectId(workspaceId: string): string {
  return `playground-${workspaceId.slice(0, 8)}`;
}
