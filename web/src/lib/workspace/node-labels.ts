import { useEffect, useMemo, useState } from 'react';

import { workspaceOpenApiPOST } from '@/lib/openapi/client.js';

const RESOLVE_LABELS_BATCH = 80;

export async function fetchWorkspaceNodeLabels(
  workspaceId: string,
  ids: string[],
): Promise<Record<string, string | null>> {
  const unique = [...new Set(ids.map((id) => id.trim()).filter(Boolean))];
  if (!unique.length) {
    return {};
  }
  const merged: Record<string, string | null> = {};
  for (let offset = 0; offset < unique.length; offset += RESOLVE_LABELS_BATCH) {
    const batch = unique.slice(offset, offset + RESOLVE_LABELS_BATCH);
    const data = await workspaceOpenApiPOST<{ labels: Record<string, string | null> }>(
      workspaceId,
      'graph/resolve-labels',
      { body: { ids: batch } },
    );
    Object.assign(merged, data.labels ?? {});
  }
  return merged;
}

/** Resolve ledger/graph labels for a set of node ids (refetches when id set changes). */
export function useWorkspaceNodeLabels(workspaceId: string | undefined, ids: string[]) {
  const [labels, setLabels] = useState<Record<string, string | null>>({});
  const idKey = useMemo(
    () => [...new Set(ids.map((id) => id.trim()).filter(Boolean))].sort().join('\0'),
    [ids],
  );

  useEffect(() => {
    if (!workspaceId || !idKey) {
      setLabels({});
      return;
    }
    const parsed = idKey.split('\0');
    void fetchWorkspaceNodeLabels(workspaceId, parsed)
      .then((next) => setLabels((prev) => ({ ...prev, ...next })))
      .catch(() => {});
  }, [workspaceId, idKey]);

  return labels;
}
