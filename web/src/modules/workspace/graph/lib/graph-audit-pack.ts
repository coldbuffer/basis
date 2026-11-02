export const KB_GRAPH_AUDIT_PACK_VERSION = 1;

export type GraphAuditPackStaging = {
  manifest: Record<string, unknown>;
  diff: Record<string, unknown>;
};

export type GraphAuditPack = {
  basis_audit_pack_version: number;
  generated_at: string;
  workspace_id: string;
  graph_export: unknown;
  graph_export_scope: { mode: 'full' } | { mode: 'subgraph'; node_ids: string[] };
  graph_audit_events: unknown[];
  graph_projection?: unknown;
  staging?: GraphAuditPackStaging;
};

export function triggerJsonFileDownload(filename: string, payload: unknown): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export async function buildGraphAuditPack(params: {
  workspaceId: string;
  nodeIds?: string[];
  staging?: GraphAuditPackStaging;
  postExport: (body: { format: 'json'; node_ids?: string[] }) => Promise<Response>;
  getAudit: () => Promise<{ events: unknown[] }>;
  getProjection?: () => Promise<unknown>;
}): Promise<GraphAuditPack> {
  const nodeIds = params.nodeIds?.filter((id) => id.trim()) ?? [];
  const exportBody =
    nodeIds.length > 0 ? { format: 'json' as const, node_ids: nodeIds } : { format: 'json' as const };

  const exportRes = await params.postExport(exportBody);
  if (!exportRes.ok) {
    const detail = await exportRes.json().catch(() => ({}));
    throw new Error(
      typeof detail === 'object' && detail && 'detail' in detail
        ? JSON.stringify(detail.detail)
        : `export failed (${exportRes.status})`,
    );
  }
  const graphExport = await exportRes.json();

  const audit = await params.getAudit();
  const pack: GraphAuditPack = {
    basis_audit_pack_version: KB_GRAPH_AUDIT_PACK_VERSION,
    generated_at: new Date().toISOString(),
    workspace_id: params.workspaceId,
    graph_export: graphExport,
    graph_export_scope:
      nodeIds.length > 0 ? { mode: 'subgraph', node_ids: nodeIds } : { mode: 'full' },
    graph_audit_events: audit.events ?? [],
  };
  if (params.staging) {
    pack.staging = params.staging;
  }
  if (params.getProjection) {
    pack.graph_projection = await params.getProjection();
  }
  return pack;
}
