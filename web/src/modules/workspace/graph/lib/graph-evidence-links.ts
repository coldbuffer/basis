import { graph } from '@/lib/workspace/graphStore.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

export type GraphEvidenceLink = {
  kind: 'sources-doc' | 'sources-chunk' | 'search';
  to: string;
};

function pickString(
  properties: Record<string, unknown> | undefined,
  keys: string[],
): string | null {
  if (!properties) return null;
  for (const key of keys) {
    const value = properties[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

function collectLedgerHintsFromGraph(nodeId: string): {
  chunkIds: string[];
  docIds: string[];
} {
  const chunkIds = new Set<string>();
  const docIds = new Set<string>();
  if (!graph.hasNode(nodeId)) {
    return { chunkIds: [], docIds: [] };
  }

  const nodeAttrs = graph.getNodeAttributes(nodeId) as {
    nodeType?: string;
    properties?: Record<string, unknown>;
  };
  const nodeProps = nodeAttrs.properties;
  const nodeChunk = pickString(nodeProps, ['chunk_id', 'evidence_chunk_id', 'chunkId']);
  if (nodeChunk) chunkIds.add(nodeChunk);
  const nodeDoc = pickString(nodeProps, [
    'doc_id',
    'document_id',
    'ledger_document_id',
    'external_key',
    'docId',
  ]);
  if (nodeDoc) docIds.add(nodeDoc);

  const visitNeighbor = (neighborId: string) => {
    if (!graph.hasNode(neighborId)) return;
    const attrs = graph.getNodeAttributes(neighborId) as {
      nodeType?: string;
      properties?: Record<string, unknown>;
    };
    const props = attrs.properties;
    const doc = pickString(props, [
      'doc_id',
      'document_id',
      'ledger_document_id',
      'external_key',
    ]);
    if (doc) docIds.add(doc);
    const type = (attrs.nodeType ?? '').toLowerCase();
    if (type.includes('doc') || type === 'document') {
      docIds.add(neighborId);
    }
  };

  graph.forEachEdge(nodeId, (_edge, attributes, source, target) => {
    const edgeProps = (attributes as { properties?: Record<string, unknown> }).properties;
    const chunk = pickString(edgeProps, ['chunk_id', 'evidence_chunk_id', 'chunkId']);
    if (chunk) chunkIds.add(chunk);
    const edgeDoc = pickString(edgeProps, ['doc_id', 'document_id', 'graph_doc_id']);
    if (edgeDoc) docIds.add(edgeDoc);
    visitNeighbor(source === nodeId ? target : source);
  });

  return {
    chunkIds: [...chunkIds],
    docIds: [...docIds],
  };
}

/** Deep links from a graph node to Basis knowledge UI (sources / search). */
export function resolveGraphNodeEvidenceLinks(
  workspaceId: string,
  nodeId: string,
  nodeType?: string | null,
  properties?: Record<string, unknown>,
): GraphEvidenceLink[] {
  const links: GraphEvidenceLink[] = [];
  const seen = new Set<string>();
  const type = (nodeType ?? '').toLowerCase();

  const chunkId = pickString(properties, [
    'chunk_id',
    'evidence_chunk_id',
    'chunkId',
  ]);
  const docId = pickString(properties, [
    'doc_id',
    'document_id',
    'doc_ref',
    'docRef',
    'ledger_document_id',
    'external_key',
    'docId',
  ]);

  const add = (link: GraphEvidenceLink) => {
    if (seen.has(link.to)) return;
    seen.add(link.to);
    links.push(link);
  };

  if (chunkId) {
    add({
      kind: 'sources-chunk',
      to: `${workspacePath(workspaceId, 'sources')}?chunk=${encodeURIComponent(chunkId)}`,
    });
  }
  if (docId) {
    add({
      kind: 'sources-doc',
      to: `${workspacePath(workspaceId, 'sources')}?doc=${encodeURIComponent(docId)}`,
    });
  }

  if (!chunkId && !docId) {
    if (type.includes('chunk')) {
      add({
        kind: 'sources-chunk',
        to: `${workspacePath(workspaceId, 'sources')}?chunk=${encodeURIComponent(nodeId)}`,
      });
    } else if (type.includes('doc') || type === 'document') {
      add({
        kind: 'sources-doc',
        to: `${workspacePath(workspaceId, 'sources')}?doc=${encodeURIComponent(nodeId)}`,
      });
    }
  }

  const graphHints = collectLedgerHintsFromGraph(nodeId);
  for (const hintChunk of graphHints.chunkIds) {
    add({
      kind: 'sources-chunk',
      to: `${workspacePath(workspaceId, 'sources')}?chunk=${encodeURIComponent(hintChunk)}`,
    });
  }
  for (const hintDoc of graphHints.docIds) {
    add({
      kind: 'sources-doc',
      to: `${workspacePath(workspaceId, 'sources')}?doc=${encodeURIComponent(hintDoc)}`,
    });
  }

  if (links.length === 0 && nodeId.trim()) {
    add({
      kind: 'search',
      to: `${workspacePath(workspaceId, 'search')}?q=${encodeURIComponent(nodeId)}`,
    });
  }

  return links;
}
