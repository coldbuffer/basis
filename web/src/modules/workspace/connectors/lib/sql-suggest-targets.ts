import type { StoredConnection } from '@/modules/workspace/connectors/lib/connector-connections.js';

export type SqlSuggestTarget = {
  provider: string;
    external_table: string;
  stream_name?: string;
};

const SQL_SERVICES = new Set(['postgres', 'mysql']);

/** Parse optional wizard-style SQL table lines into suggest API targets. */
export function buildSqlSuggestTargets(
  connections: StoredConnection[],
  sqlTableInput: string,
): SqlSuggestTarget[] {
  const lines = sqlTableInput
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return [];
  }
  const sqlConnections = connections.filter((c) => SQL_SERVICES.has(c.service));
  if (sqlConnections.length === 0) {
    return [];
  }
  const targets: SqlSuggestTarget[] = [];
  for (const line of lines) {
    const [maybeService, table] = line.includes(':')
      ? line.split(':', 2).map((x) => x.trim())
      : [null, line];
    const conn =
      (maybeService
        ? sqlConnections.find((c) => c.service === maybeService)
        : sqlConnections[0]) ?? sqlConnections[0];
    if (table) {
      targets.push({
        provider: conn.service,
                external_table: table,
      });
    }
  }
  return targets;
}
