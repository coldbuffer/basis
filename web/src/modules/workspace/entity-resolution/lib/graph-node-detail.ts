import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

export type GraphNodeRecord = {
  id: string;
  type?: string;
  content?: string;
  properties?: Record<string, unknown>;
};

export async function fetchWorkspaceGraphNode(
  workspaceId: string,
  nodeId: string,
): Promise<GraphNodeRecord | null> {
  const body = await workspaceOpenApiGET<{ node: GraphNodeRecord | null }>(
    workspaceId,
    `graph/nodes/${encodeURIComponent(nodeId)}`,
  );
  return body.node ?? null;
}

/** Flatten node fields for side-by-side merge review. */
export function graphNodeFieldMap(node: GraphNodeRecord | null): Record<string, string> {
  if (!node) return {};
  const out: Record<string, string> = {
    id: node.id,
    type: String(node.type ?? ''),
    content: String(node.content ?? ''),
  };
  const props = node.properties ?? {};
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined) continue;
    out[key] =
      typeof value === 'object' ? JSON.stringify(value) : String(value);
  }
  return out;
}

export function diffGraphNodeFields(
  primary: Record<string, string>,
  duplicate: Record<string, string>,
): Array<{ key: string; primary: string; duplicate: string; differs: boolean }> {
  const keys = new Set([...Object.keys(primary), ...Object.keys(duplicate)]);
  return [...keys]
    .sort()
    .map((key) => {
      const a = primary[key] ?? '';
      const b = duplicate[key] ?? '';
      return { key, primary: a, duplicate: b, differs: a !== b };
    })
    .filter((row) => row.primary || row.duplicate);
}
