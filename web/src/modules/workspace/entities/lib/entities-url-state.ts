import { workspacePath } from '@/lib/nav/nav-config.js';

const STATEMENT_PARAM = 'statement';
const TAB_PARAM = 'tab';

export type EntitiesTab = 'entities' | 'derived';

export function parseEntitiesUrlState(search: string): {
  statementId?: string;
  tab: EntitiesTab;
} {
  const sp = new URLSearchParams(search);
  const statementId = sp.get(STATEMENT_PARAM)?.trim();
  const rawTab = sp.get(TAB_PARAM)?.trim();
  const tab: EntitiesTab = rawTab === 'derived' ? 'derived' : 'entities';
  return {
    statementId: statementId || undefined,
    tab: statementId ? 'entities' : tab,
  };
}

/** Deep-link to Entities with a ledger statement highlighted (F-RUL-03). */
export function entitiesStatementPath(workspaceId: string, statementId: string): string {
  const params = new URLSearchParams({ [STATEMENT_PARAM]: statementId });
  return `${workspacePath(workspaceId, 'entities')}?${params.toString()}`;
}
