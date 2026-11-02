const STORAGE_PREFIX = "sema.graphIncludeArchived.v1:";

export function loadGraphIncludeArchived(workspaceId: string): boolean {
  try {
    return localStorage.getItem(`${STORAGE_PREFIX}${workspaceId}`) === "1";
  } catch {
    return false;
  }
}

export function saveGraphIncludeArchived(workspaceId: string, enabled: boolean): void {
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${workspaceId}`, enabled ? "1" : "0");
  } catch {
    // ignore
  }
}

export function isArchivedProjectionNode(properties: Record<string, unknown> | undefined): boolean {
  if (!properties) return false;
  return String(properties.status ?? "").trim().toLowerCase() === "archived";
}
