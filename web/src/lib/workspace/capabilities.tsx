import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useLocation } from 'react-router-dom';
import { devMessage } from '@/i18n/dev-messages.js';
import type { WorkspaceNavKey } from '@/lib/nav/nav-config.js';
import { isSetupWorkspaceId } from '@/lib/workspace/active-id.js';
import { parseWorkspaceIdFromPath } from '@/lib/nav/nav-config.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

export type WorkspaceCapabilities = {
  workspace_id: string;
  role: string;
  graph: boolean;
  graph_write: boolean;
  temporal: boolean;
  decisions: boolean;
  sparql: boolean;
  reasoning: boolean;
  enrichment: boolean;
  review: boolean;
  direct_graph_merge: boolean;
  direct_graph_import: boolean;
  import_export: boolean;
  provenance: boolean;
  vocabulary: boolean;
  mappings: boolean;
  agent_memory: boolean;
  graph_runtime: boolean;
  diagnostic: string | null;
  graph_page_max_nodes?: number;
  graph_page_max_edges?: number;
  upload_max_bytes?: number;
  import_max_bytes?: number;
  ingest_max_inflight?: number;
  ingest_max_pending?: number;
  processing_job_timeout_seconds?: number;
  ingest_max_extract_chars?: number;
};

type WorkspaceCapabilitiesContextValue = {
  workspaceId: string | null;
  caps: WorkspaceCapabilities | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

const WorkspaceCapabilitiesContext = createContext<WorkspaceCapabilitiesContextValue | null>(null);

export function WorkspaceCapabilitiesProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const workspaceId = parseWorkspaceIdFromPath(pathname);
  const [caps, setCaps] = useState<WorkspaceCapabilities | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!workspaceId || isSetupWorkspaceId(workspaceId)) {
      setCaps(null);
      return;
    }
    setLoading(true);
    try {
      const body = await workspaceOpenApiGET<WorkspaceCapabilities>(workspaceId, 'capabilities');
      setCaps(body);
    } catch {
      setCaps(null);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ workspaceId, caps, loading, refresh }),
    [workspaceId, caps, loading, refresh],
  );

  return (
    <WorkspaceCapabilitiesContext.Provider value={value}>{children}</WorkspaceCapabilitiesContext.Provider>
  );
}

export function useWorkspaceCapabilitiesOptional(): WorkspaceCapabilitiesContextValue | null {
  return useContext(WorkspaceCapabilitiesContext);
}

export function useWorkspaceCapabilities(): WorkspaceCapabilitiesContextValue {
  const ctx = useWorkspaceCapabilitiesOptional();
  if (!ctx) {
    throw new Error(devMessage('useWorkspaceCapabilities'));
  }
  return ctx;
}

/** Whether a workspace sidebar segment should be navigable for the current capability set. */
export function workspaceNavSegmentEnabled(segment: string, caps: WorkspaceCapabilities | null): boolean {
  if (!caps) return true;
  if (segment === 'connectors' || segment.startsWith('connectors/')) return true;
  if (segment === 'graph-diff') return caps.graph;
  if (segment === 'quality') return caps.review;
  if (segment === 'analyze') {
    return caps.sparql || caps.reasoning;
  }
  const key = segment as WorkspaceNavKey;
  switch (key) {
    case 'graph':
    case 'search':
      return caps.graph;
    case 'lineage':
      return caps.provenance && caps.graph;
    case 'ontology':
      return caps.graph_runtime && caps.graph;
    case 'sparql':
      return caps.sparql;
    case 'reasoning':
      return caps.reasoning;
    case 'review':
      return caps.review;
    case 'log':
      return caps.review;
    case 'sources':
    case 'processing':
    case 'entities':
      return true;
    case 'vocabulary':
      return caps.vocabulary;
    case 'alerts':
    case 'mappings':
    case 'integration':
    case 'settings':
      return true;
    default:
      return true;
  }
}
