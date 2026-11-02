import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { errorFromApiResponse } from '@/lib/errors/api-error.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { workspaceOpenApiGET, workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { Button } from '@/components/ui/button.js';
import { Input } from '@/components/ui/input.js';
import { useI18n } from '@/i18n/context.js';
import { exWsPageRow, exWsScrollFill, exWsSplitMain, exWsSplitSidebar } from '@/lib/ui-classes/ws-ui.js';
import { cn } from '@/lib/utils.js';

const THEME_CSS = `
  .basis-lineage-flow .react-flow { background: var(--background); }
  .basis-lineage-flow .react-flow__node-group {
    background: color-mix(in oklab, var(--primary) 6%, transparent);
    border: 1px dashed color-mix(in oklab, var(--primary) 28%, transparent);
    border-radius: 10px;
  }
  .basis-lineage-flow .react-flow__node-default {
    background: var(--card);
    color: var(--card-foreground);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    white-space: pre-wrap;
    font-size: 12px;
  }
`;

type ProvenancePayload = {
  nodes: Array<{ id: string; parent_id: string; label: string; prov_type: string }>;
  edges: Array<{ id: string; source: string; target: string; label: string }>;
  message?: string;
};

export function LineagePanel({
  workspaceId,
  initialNodeId,
  className,
}: {
  workspaceId: string;
  initialNodeId?: string | null;
  className?: string;
}) {
  const apiError = useApiErrorMessage();
  const { t, locale } = useI18n();
  const copy = t.lineage.page;
  const [searchParams, setSearchParams] = useSearchParams();
  const [nodes, setNodes] = useState<any[]>([]);
  const [edges, setEdges] = useState<any[]>([]);
  const [records, setRecords] = useState<ProvenancePayload['nodes']>([]);
  const [searchId, setSearchId] = useState(initialNodeId ?? '');
  const [activeId, setActiveId] = useState(initialNodeId ?? '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    if (initialNodeId) {
      setSearchId(initialNodeId);
      setActiveId(initialNodeId);
    }
  }, [initialNodeId]);

  const downloadReport = async (format: 'json' | 'markdown') => {
    if (!activeId) return;
    const response = await workspaceOpenApiResponse('GET', workspaceId, 'provenance/report', {
      params: {
        query: { node_id: activeId, format },
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw errorFromApiResponse(response.status, body, t.lineage.page.provenance_download_failed);
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${activeId}_provenance.${format === 'markdown' ? 'md' : 'json'}`;
    document.body.appendChild(anchor);
    anchor.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(anchor);
  };

  useEffect(() => {
    let ignore = false;
    if (!activeId) {
      setNodes([]);
      setEdges([]);
      setRecords([]);
      setLoading(false);
      return;
    }

    const xLanes = [
      { id: 'group_agent', type: 'group', position: { x: 50, y: 50 }, style: { width: 800, height: 120 } },
      { id: 'group_activity', type: 'group', position: { x: 50, y: 200 }, style: { width: 800, height: 120 } },
      { id: 'group_entity', type: 'group', position: { x: 50, y: 350 }, style: { width: 800, height: 120 } },
    ];

    void (async () => {
      setError('');
      setLoading(true);
      try {
        const data = await workspaceOpenApiGET<ProvenancePayload>(workspaceId, 'provenance', {
          params: { query: { node_id: activeId } },
        });
        if (data.message) setError(data.message);

        const counters: Record<string, number> = {
          group_agent: 0,
          group_activity: 0,
          group_entity: 0,
        };

        const mappedNodes = data.nodes.map((n) => {
          const c = counters[n.parent_id] ?? 0;
          counters[n.parent_id] = c + 1;
          return {
            id: n.id,
            data: { label: `${n.label}\n(${n.prov_type})` },
            position: { x: 50 + c * 180, y: 30 },
            parentId: n.parent_id,
            extent: 'parent' as const,
            type: 'default',
          };
        });

        const mappedEdges = data.edges.map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          label: e.label,
          animated: true,
          style: { stroke: 'var(--primary)' },
        }));

        if (!ignore) {
          setRecords(data.nodes);
          setNodes([...xLanes, ...mappedNodes]);
          setEdges(mappedEdges);
        }
      } catch (err) {
        if (!ignore) {
          setRecords([]);
          setNodes([]);
          setEdges([]);
          setError(apiError(err));
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    })();

    return () => {
      ignore = true;
    };
  }, [activeId, apiError, workspaceId, locale, t.lineage.page.fetch_failed]);

  function traceNode(raw: string) {
    const id = raw.trim();
    setSearchId(id);
    setActiveId(id);
    const next = new URLSearchParams(searchParams);
    if (id) next.set('node', id);
    else next.delete('node');
    setSearchParams(next, { replace: true });
  }

  return (
    <div className={cn('basis-lineage-flow relative flex min-h-0 flex-1 flex-col', className)}>
      <style>{THEME_CSS}</style>
      <div className={exWsPageRow}>
        <div className={exWsSplitSidebar}>
          <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
            <PublicIcon name="path" size={13} className="shrink-0 text-muted-foreground" />
            <Input
              value={searchId}
              onChange={(event) => setSearchId(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') traceNode(searchId);
              }}
              placeholder={copy.node_id}
              aria-label={copy.node_id}
              className="h-8 min-w-0 flex-1 font-mono text-xs"
            />
          </div>
          <div className={exWsScrollFill}>
            {!activeId ? (
              <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                <PublicIcon name="path" size={18} className="mb-2 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">{copy.empty_title}</p>
                <p className="mt-1 max-w-xs text-[11px] leading-snug text-muted-foreground">{copy.empty_body}</p>
              </div>
            ) : records.length === 0 && !loading ? (
              <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                <PublicIcon name="path" size={18} className="mb-2 text-muted-foreground" />
                <p className="text-sm font-medium text-foreground">{copy.empty_title}</p>
                <p className="mt-1 max-w-xs text-[11px] leading-snug text-muted-foreground">{copy.empty_list}</p>
              </div>
            ) : (
              records.map((record) => (
                <div key={record.id} className="border-b border-border px-4 py-2.5">
                  <p className="truncate text-[13px] text-foreground">{record.label || record.id}</p>
                  <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">{record.prov_type}</p>
                </div>
              ))
            )}
          </div>
          <div className="flex h-12 shrink-0 items-center gap-2 border-t border-border px-3">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 px-2 text-xs"
              disabled={!activeId || loading}
              onClick={() => void downloadReport('json').catch((err) => setError(apiError(err)))}
            >
              <PublicIcon name="file-code" size={14} />
              {copy.json}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-8 px-2 text-xs"
              disabled={!activeId || loading}
              onClick={() => void downloadReport('markdown').catch((err) => setError(apiError(err)))}
            >
              <PublicIcon name="file-01" size={14} />
              {copy.markdown}
            </Button>
            <Button
              type="button"
              size="sm"
              className="ml-auto h-8"
              disabled={loading || (!searchId.trim() && !activeId)}
              onClick={() => traceNode(searchId)}
            >
              {loading ? <PublicIcon name="loader-01" size={14} className="animate-spin" /> : <PublicIcon name="path" size={14} />}
              {loading ? copy.tracing : copy.trace}
            </Button>
          </div>
        </div>

        <div className={exWsSplitMain}>
          <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
            <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">{copy.graph}</span>
            {activeId ? <span className="min-w-0 truncate font-mono text-[11px] text-muted-foreground">{activeId}</span> : null}
            {!loading && records.length > 0 ? (
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">{records.length}</span>
            ) : null}
          </div>
          {error ? <p className="shrink-0 border-b border-border px-4 py-2 text-sm text-destructive">{error}</p> : null}
          {activeId && nodes.length > 0 ? (
            <div className="relative min-h-0 flex-1">
              <ReactFlow nodes={nodes} edges={edges} fitView>
                <Background gap={24} />
                <Controls />
              </ReactFlow>
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 text-center">
              {loading ? (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <PublicIcon name="loader-01" size={14} className="animate-spin" />
                  {copy.tracing}
                </p>
              ) : (
                <>
                  <PublicIcon name="path" size={18} className="mb-2 text-muted-foreground" />
                  <p className="text-sm font-medium text-foreground">{copy.empty_title}</p>
                  <p className="mt-1 max-w-xs text-[11px] leading-snug text-muted-foreground">{copy.empty_body}</p>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
