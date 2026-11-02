/** Shared helpers for workspace BOCP connection pickers and mapping routes. */

import { workspaceConnectorPanelPath } from '@/lib/nav/nav-config.js';

export type StoredConnection = {
  workspace_id: string;
  service: string;
  auth_type: string;
  connection_config: Record<string, unknown>;
  account_profile: Record<string, unknown>;
  revision: number;
  updated_at: string;
  has_credentials: boolean;
  connection_scope?: 'workspace' | 'end_user';
  subject_id?: string | null;
};

export function isWorkspaceConnection(conn: StoredConnection): boolean {
  return (conn.connection_scope ?? 'workspace') === 'workspace';
}

export function isEndUserConnection(conn: StoredConnection): boolean {
  return conn.connection_scope === 'end_user';
}

/** Stable React key / checking state key for a vault row. */
export function connectionStorageKey(conn: StoredConnection): string {
  const scope = conn.connection_scope ?? 'workspace';
  const subject = scope === 'end_user' ? (conn.subject_id ?? '').trim() : '';
  return `${scope}\u001f${subject}\u001f${conn.service}`;
}

/** Services that already use workspace-shared vault rows (blocks end_user for same service). */
export function workspaceSharedServiceNames(connections: StoredConnection[]): Set<string> {
  const names = new Set<string>();
  for (const conn of connections) {
    if ((conn.connection_scope ?? 'workspace') === 'workspace') {
      names.add(conn.service);
    }
  }
  return names;
}

export function partitionConnectionsByScope(connections: StoredConnection[]): {
  workspace: StoredConnection[];
  endUser: StoredConnection[];
} {
  const workspace: StoredConnection[] = [];
  const endUser: StoredConnection[] = [];
  for (const conn of connections) {
    if (isEndUserConnection(conn)) {
      endUser.push(conn);
    } else {
      workspace.push(conn);
    }
  }
  const byService = (a: StoredConnection, b: StoredConnection) =>
    a.service.localeCompare(b.service);
  workspace.sort(byService);
  endUser.sort(
    (a, b) => (a.subject_id ?? '').localeCompare(b.subject_id ?? '') || byService(a, b),
  );
  return { workspace, endUser };
}

/** Workspace + end_user vault rows for a single authorization list (scope badge distinguishes). */
export function mergeAuthorizationsForList(connections: StoredConnection[]): StoredConnection[] {
  const { workspace, endUser } = partitionConnectionsByScope(connections);
  const merged = [...workspace, ...endUser];
  merged.sort((a, b) => {
    const byService = a.service.localeCompare(b.service);
    if (byService !== 0) {
      return byService;
    }
    const scopeA = a.connection_scope ?? 'workspace';
    const scopeB = b.connection_scope ?? 'workspace';
    if (scopeA !== scopeB) {
      return scopeA === 'workspace' ? -1 : 1;
    }
    if (scopeA === 'end_user') {
      return (a.subject_id ?? '').localeCompare(b.subject_id ?? '');
    }
    return 0;
  });
  return merged;
}

/** Workspace-scoped connections grouped by connector service (catalog cards). */
export function workspaceConnectionsByService(
  connections: StoredConnection[],
): Map<string, StoredConnection[]> {
  const map = new Map<string, StoredConnection[]>();
  for (const conn of connections) {
    const scope = conn.connection_scope ?? 'workspace';
    if (scope !== 'workspace') {
      continue;
    }
    const list = map.get(conn.service) ?? [];
    list.push(conn);
    map.set(conn.service, list);
  }
  return map;
}

export function workspaceConnectionOptionKey(conn: Pick<StoredConnection, 'service'>): string {
  return conn.service;
}

export const connectorConnectionSelectKey = workspaceConnectionOptionKey;

export function connectorConnectionOptionLabel(conn: StoredConnection): string {
  const scope = conn.connection_scope ?? 'workspace';
  if (scope === 'end_user' && conn.subject_id) {
    return `${conn.service} · ${conn.subject_id}`;
  }
  return conn.service;
}

export function resolveStoredConnectionFromOptionKey(
  key: string,
  connections: StoredConnection[],
): StoredConnection | null {
  const { service } = parseWorkspaceConnectionOptionKey(key);
  return connections.find((c) => c.service === service) ?? null;
}

export function parseWorkspaceConnectionOptionKey(key: string): { service: string } {
  const sep = key.indexOf('\u001f');
  if (sep < 0) {
    return { service: key };
  }
  return { service: key.slice(0, sep) };
}

/** Resolve service (and optional scope) from a picker key; ignores legacy name segments. */
export function connectionIdentityFromOptionKey(
  key: string,
  connections?: StoredConnection[],
): { service: string } {
  const { service } = parseWorkspaceConnectionOptionKey(key);
  if (connections?.length) {
    const match = connections.find((c) => c.service === service);
    if (match) {
      return { service: match.service };
    }
  }
  return { service };
}

export function defaultConnectorStreamName(service: string): string {
  if (service === 'postgres' || service === 'mysql') {
    return 'table_records';
  }
  return 'records';
}

export function workspaceConnectorMappingEditPath(workspaceId: string, mappingId: string): string {
  return `/workspaces/${workspaceId}/connectors/mappings/${mappingId}/edit`;
}

export function workspaceConnectorMappingNewPath(
  workspaceId: string,
  opts?: { service?: string },
): string {
  const base = `/workspaces/${workspaceId}/connectors/mappings/new`;
  if (!opts?.service) {
    return base;
  }
  const params = new URLSearchParams({ service: opts.service });
  return `${base}?${params.toString()}`;
}

export function workspaceConnectorsMappingsTabPath(workspaceId: string): string {
  return workspaceConnectorPanelPath(workspaceId, 'mappings');
}
