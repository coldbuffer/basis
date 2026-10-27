import { lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { WorkspaceConsoleShell } from '@/components/app/shared/workspace/frame/ws-console-shell.js';
import { OntologyWorkspaceCatalogProvider } from '@/components/app/shared/workspace/ontology-workspace-context.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { cn } from '@/lib/utils.js';
import { wsPage } from '@/lib/ui-classes/console-ws.js';

const ShaclStudio = lazy(() =>
  import('@/modules/ontology/components/shacl-studio.js').then((module) => ({
    default: module.ShaclStudio,
  })),
);

function OntologySuspenseFallback({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4" />
      {label}
    </div>
  );
}

export function OntologyShaclPanel({
  workspaceId,
  className,
  initialOntologyUri,
}: {
  workspaceId: string;
  className?: string;
  initialOntologyUri?: string | null;
}) {
  const { t } = useI18n();
  const navigate = useNavigate();

  const onJumpToGraphNode = (nodeId: string) => {
    navigate(`${workspacePath(workspaceId, 'graph')}?focus=${encodeURIComponent(nodeId)}`);
  };

  return (
    <WorkspaceConsoleShell workspaceId={workspaceId} className={className} feature="sparql">
      <OntologyWorkspaceCatalogProvider workspaceId={workspaceId}>
        <Suspense fallback={<OntologySuspenseFallback label={t.ontology.page.loading_shacl} />}>
          <div className={cn(wsPage, 'min-h-0 flex-1')}>
            <ShaclStudio onJumpToNode={onJumpToGraphNode} initialOntologyUri={initialOntologyUri} />
          </div>
        </Suspense>
      </OntologyWorkspaceCatalogProvider>
    </WorkspaceConsoleShell>
  );
}
