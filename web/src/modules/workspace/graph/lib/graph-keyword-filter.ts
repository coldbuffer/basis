import type { NodeAttributes } from '@/lib/workspace/graphStore';

export function normalizeKeywordFilter(query: string): string {
  return query.trim().toLocaleLowerCase();
}

export function nodeMatchesKeywordFilter(
  attrs: Pick<NodeAttributes, "label" | "content" | "nodeType">,
  nodeId: string,
  normalizedQuery: string,
): boolean {
  if (!normalizedQuery) {
    return true;
  }
  const haystack = [attrs.label, attrs.content, attrs.nodeType, nodeId]
    .filter((part) => typeof part === "string" && part.length > 0)
    .join("\0")
    .toLocaleLowerCase();
  return haystack.includes(normalizedQuery);
}

export function isNodeKeywordSuppressed(
  attrs: Pick<NodeAttributes, "label" | "content" | "nodeType">,
  nodeId: string,
  normalizedQuery: string,
): boolean {
  return normalizedQuery.length > 0 && !nodeMatchesKeywordFilter(attrs, nodeId, normalizedQuery);
}
