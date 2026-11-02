import { entitiesStatementPath } from '@/modules/workspace/entities/lib/entities-url-state.js';
import { graphPath } from '@/modules/workspace/graph/lib/graph-url-state.js';

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type DerivedFactPremise = {
  premise_kind?: string;
  premise_id?: string;
};

/** Deep-link target for a proof premise row (F-RUL-03). */
export function hrefForDerivedFactPremise(
  workspaceId: string,
  premise: DerivedFactPremise,
): string | null {
  const id = premise.premise_id?.trim();
  if (!id) return null;
  const kind = premise.premise_kind?.trim().toLowerCase();
  if (kind === 'statement' && UUID_RE.test(id)) {
    return entitiesStatementPath(workspaceId, id);
  }
  if (UUID_RE.test(id)) {
    return graphPath(workspaceId, { focus: id });
  }
  return null;
}
