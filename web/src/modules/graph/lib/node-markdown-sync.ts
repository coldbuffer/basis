import { fmt } from "@/i18n/format.js";
import { errorFromApiResponse } from "@/lib/errors/api-error.js";

import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { graphCopy, type GraphScreenLocale } from '../i18n/screen-copy.js';

export interface NodeMarkdownAttributeUpdate {
  label: string;
  content: string;
  properties: Record<string, unknown>;
}

export interface GraphNodeMarkdownSnapshot {
  id: string;
  type: string;
  content: string;
  properties: Record<string, unknown>;
  valid_from: string | null;
  valid_until: string | null;
}

export interface SavedNodeMarkdownAttributeUpdate extends NodeMarkdownAttributeUpdate {
  nodeType: string;
  valid_from: string | null;
  valid_until: string | null;
}

export class NodeMarkdownRefreshGuard {
  private readonly generations = new Map<string, number>();

  begin(nodeId: string): number {
    const generation = (this.generations.get(nodeId) ?? 0) + 1;
    this.generations.set(nodeId, generation);
    return generation;
  }

  invalidate(nodeId: string): void {
    this.begin(nodeId);
  }

  isCurrent(nodeId: string, generation: number): boolean {
    return this.generations.get(nodeId) === generation;
  }
}

export function buildNodeMarkdownAttributeUpdate(
  nodeId: string,
  content: string,
  properties: Record<string, unknown>,
): NodeMarkdownAttributeUpdate {
  return {
    label: content || nodeId,
    content,
    properties: {
      ...properties,
      content,
    },
  };
}

export async function readNodeMarkdownAttributeUpdate(
  nodeId: string,
  workspaceId: string,
  locale: GraphScreenLocale = "en",
): Promise<SavedNodeMarkdownAttributeUpdate> {
  const response = await workspaceOpenApiResponse(
    'GET',
    workspaceId,
    `graph/nodes/${encodeURIComponent(nodeId)}`,
  );
  const payload = (await response.json().catch(() => ({}))) as
    | GraphNodeMarkdownSnapshot
    | { node: GraphNodeMarkdownSnapshot };
  if (!response.ok) {
    throw errorFromApiResponse(
      response.status,
      payload,
      fmt(graphCopy(locale, "apiNodeRefreshFailed"), { status: response.status }),
      locale,
    );
  }
  const node = ("node" in payload && payload.node ? payload.node : payload) as GraphNodeMarkdownSnapshot;
  if (node.id !== nodeId) {
    throw new Error(graphCopy(locale, "apiNodeRefreshMismatch"));
  }

  return {
    ...buildNodeMarkdownAttributeUpdate(
      node.id,
      node.content,
      node.properties ?? {},
    ),
    nodeType: node.type,
    valid_from: node.valid_from ?? null,
    valid_until: node.valid_until ?? null,
  };
}
