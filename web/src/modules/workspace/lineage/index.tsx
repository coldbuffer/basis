import { useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { WorkspaceHostProvider } from '@/lib/workspace/ws-http.js';
import { buildWorkspaceHttpConfig } from '@/lib/workspace/ws-host.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { LineagePanel } from './components/lineage-panel.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { cn } from '@/lib/utils.js';

export function LineagePage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const initialNodeId = searchParams.get('node');
  const { t, locale } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();
  const config = useMemo(() => (id ? buildWorkspaceHttpConfig(id, locale) : null), [id, locale]);

  if (!id) return null;

  const panel =
    !capsLoading && caps && !caps.provenance ? (
      <WorkspaceUnavailable workspaceId={id} feature="lineage" />
    ) : (
      <div
        className={cn(
          'basis-ws-console basis-lineage-shell relative flex min-h-0 w-full flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background',
        )}
        data-workspace-id={id}
      >
        {config ? (
          <WorkspaceHostProvider config={config}>
            <LineagePanel workspaceId={id} initialNodeId={initialNodeId} className="min-h-0 flex-1" />
          </WorkspaceHostProvider>
        ) : null}
      </div>
    );

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.lineage.menu.lineage },
      ]}
      className="min-h-0 overflow-hidden"
    >
      {panel}
    </ConsolePageLayout>
  );
}
