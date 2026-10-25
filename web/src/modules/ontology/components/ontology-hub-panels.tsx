import { lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { WorkspaceConsoleShell } from '@/components/app/shared/workspace/frame/ws-console-shell.js';
import { OntologyWorkspaceCatalogProvider } from '@/modules/ontology/components/ontology-workspace-context.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { cn } from '@/lib/utils.js';
import { wsPage } from '@/lib/ui-classes/console-ws.js';
import type { OntologyInteriorPanel } from '@/modules/ontology/pages/ontology-screen.js';

const OntologyScreen = lazy(() =>
  import('@/modules/ontology/pages/ontology-screen.js').then((module) => ({
    default: module.OntologyScreen,
  })),
);

const AlignmentsPanel = lazy(() =>
  import('@/modules/ontology/components/alignments-panel.js').then((module) => ({
    default: module.AlignmentsPanel,
  })),
);

const ShaclStudio = lazy(() =>
  import('@/modules/ontology/components/shacl-studio.js').then((module) => ({
    default: module.ShaclStudio,
  })),
);

const VersionsPanel = lazy(() =>
  import('@/modules/ontology/components/versions-panel.js').then((module) => ({
    default: module.VersionsPanel,
  })),
);

export type OntologyHubPageActions = {
  openLoadOntology: () => void;
};

function OntologySuspenseFallback({ label }: { label: string }) {
  return (
    <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4" />
      {label}
    </div>
  );
}

export function OntologyRegistryPanel({
  workspaceId,
  className,
  panel,
  onPageActionsChange,
  onFixInEditor,
}: {
  workspaceId: string;
  className?: string;
  panel: OntologyInteriorPanel;
  onPageActionsChange?: (actions: OntologyHubPageActions | null) => void;
  onFixInEditor?: (entityUri: string) => void;
}) {
  const { t } = useI18n();
  const pageActionsHosted = Boolean(onPageActionsChange) && panel === 'registry';

  return (
    <WorkspaceConsoleShell workspaceId={workspaceId} className={className} feature="sparql">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <Suspense fallback={<OntologySuspenseFallback label={t.ontology.page.loading_ontology} />}>
          <OntologyScreen
            workspaceId={workspaceId}
            panel={panel}
            pageActionsHosted={pageActionsHosted}
            onPageActionsChange={onPageActionsChange}
            onFixInEditor={onFixInEditor}
          />
        </Suspense>
      </div>
    </WorkspaceConsoleShell>
  );
}

export function OntologyAlignmentsPanel({
  workspaceId,
  className,
}: {
  workspaceId: string;
  className?: string;
}) {
  const { t } = useI18n();

  return (
    <WorkspaceConsoleShell workspaceId={workspaceId} className={className} feature="sparql">
      <OntologyWorkspaceCatalogProvider workspaceId={workspaceId}>
        <Suspense fallback={<OntologySuspenseFallback label={t.ontology.page.loading_alignments} />}>
          <div className={cn(wsPage, 'min-h-0 flex-1')}>
            <AlignmentsPanel />
          </div>
        </Suspense>
      </OntologyWorkspaceCatalogProvider>
    </WorkspaceConsoleShell>
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

export function OntologyVersionsPanel({
  workspaceId,
  className,
}: {
  workspaceId: string;
  className?: string;
}) {
  const { t } = useI18n();

  return (
    <WorkspaceConsoleShell workspaceId={workspaceId} className={className} feature="sparql">
      <OntologyWorkspaceCatalogProvider workspaceId={workspaceId}>
        <Suspense fallback={<OntologySuspenseFallback label={t.ontology.page.loading_ontology_versions} />}>
          <VersionsPanel />
        </Suspense>
      </OntologyWorkspaceCatalogProvider>
    </WorkspaceConsoleShell>
  );
}
