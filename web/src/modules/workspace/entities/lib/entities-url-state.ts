import { workspacePath } from '@/lib/nav/nav-config.js';

const STATEMENT_PARAM = 'statement';

export function parseEntitiesUrlState(search: string): { statementId?: string } {
  const statementId = new URLSearchParams(search).get(STATEMENT_PARAM)?.trim();
  return { statementId: statementId || undefined };
}

/** Deep-link to Entities with a ledger statement highlighted (F-RUL-03). */
export function entitiesStatementPath(workspaceId: string, statementId: string): string {
  const params = new URLSearchParams({ [STATEMENT_PARAM]: statementId });
  return `${workspacePath(workspaceId, 'entities')}?${params.toString()}`;
}
