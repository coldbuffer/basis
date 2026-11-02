import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { isSetupWorkspaceId, resolveSidebarWorkspaceId } from '@/lib/workspace/active-id.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { isWorkspaceScopedPath, parseWorkspaceIdFromPath } from '@/lib/nav/nav-config.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';

type JobsResponse = { jobs: Array<{ status: string }> };

function resolveWorkspaceId(pathname: string, workspaces: ReturnType<typeof useWorkspaceCatalog>['workspaces']): string | null {
  const workspaceScoped = isWorkspaceScopedPath(pathname);
  const pathWorkspaceId = parseWorkspaceIdFromPath(pathname);
  const navWorkspaceId = resolveSidebarWorkspaceId(pathname, workspaces);
  const id = pathWorkspaceId && pathWorkspaceId !== 'all' && workspaceScoped ? pathWorkspaceId : navWorkspaceId;
  if (!id || isSetupWorkspaceId(id)) return null;
  return id;
}

/** Failed ingest jobs for sidebar badge (F-SRC-08 ops visibility). */
export function useWorkspaceFailedProcessingCount(): number {
  const { pathname } = useLocation();
  const { workspaces } = useWorkspaceCatalog();
  const workspaceId = resolveWorkspaceId(pathname, workspaces);
  const [failed, setFailed] = useState(0);

  const refresh = useCallback(async () => {
    if (!workspaceId) {
      setFailed(0);
      return;
    }
    try {
      const data = await workspaceOpenApiGET<JobsResponse>(workspaceId, 'ingest/jobs', {
        params: { query: { limit: 50 } },
      });
      setFailed(data.jobs.filter((job) => job.status === 'failed').length);
    } catch {
      /* non-blocking */
    }
  }, [workspaceId]);

  useEffect(() => {
    void refresh();
    if (!workspaceId) return;
    const timer = window.setInterval(() => void refresh(), 30_000);
    return () => window.clearInterval(timer);
  }, [workspaceId, refresh]);

  useEffect(() => {
    const onJobs = () => void refresh();
    window.addEventListener('workspace-processing-changed', onJobs);
    return () => window.removeEventListener('workspace-processing-changed', onJobs);
  }, [refresh]);

  return failed;
}
