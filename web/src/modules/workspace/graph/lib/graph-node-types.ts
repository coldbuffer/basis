import type Graph from "graphology";

import type { NodeAttributes } from '@/lib/workspace/graphStore';

export type GraphNodeTypeCount = {
  type: string;
  count: number;
};

const NODE_TYPE_ORDER = ["document", "entity", "literal", "owl:Ontology", "community"];

export function nodeTypeOf(attributes: Pick<NodeAttributes, "nodeType"> | undefined): string {
  const type = attributes?.nodeType;
  return typeof type === "string" && type.trim() ? type : "entity";
}

export function isNodeTypeSuppressed(nodeType: string | undefined, hiddenTypes: ReadonlySet<string>): boolean {
  return hiddenTypes.size > 0 && hiddenTypes.has(nodeType && nodeType.trim() ? nodeType : "entity");
}

export function collectNodeTypeCounts(graph: Graph): GraphNodeTypeCount[] {
  const counts = new Map<string, number>();
  graph.forEachNode((_id, attributes) => {
    const type = nodeTypeOf(attributes as NodeAttributes);
    counts.set(type, (counts.get(type) ?? 0) + 1);
  });
  return sortNodeTypeCounts([...counts.entries()].map(([type, count]) => ({ type, count })));
}

/** Keep loaded-graph types, and append display-only types such as community groups. */
export function mergeNodeTypeCounts(
  base: GraphNodeTypeCount[],
  extra: GraphNodeTypeCount[],
): GraphNodeTypeCount[] {
  const seen = new Set(base.map((item) => item.type));
  const merged = [...base];
  for (const item of extra) {
    if (!seen.has(item.type)) {
      merged.push(item);
    }
  }
  return sortNodeTypeCounts(merged);
}

function sortNodeTypeCounts(items: GraphNodeTypeCount[]): GraphNodeTypeCount[] {
  return [...items].sort((left, right) => {
    const leftOrder = NODE_TYPE_ORDER.indexOf(left.type);
    const rightOrder = NODE_TYPE_ORDER.indexOf(right.type);
    if (leftOrder !== -1 || rightOrder !== -1) {
      if (leftOrder === -1) return 1;
      if (rightOrder === -1) return -1;
      return leftOrder - rightOrder;
    }
    return right.count - left.count || left.type.localeCompare(right.type);
  });
}
