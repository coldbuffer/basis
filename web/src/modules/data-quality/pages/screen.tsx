import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { GovernanceConfigPanel } from '@/modules/data-quality/components/governance-config-panel.js';
import { OntologyShaclPanel } from '@/components/app/shared/workspace/ontology-shacl-panel.js';
import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath, workspaceReviewPath } from '@/lib/nav/nav-config.js';
import { workspaceOntologyHubPath } from '@/modules/analyze/lib/hub-route.js';

type QualitySection = 'scan' | 'structure';

function parseScrollTarget(raw: string | null): QualitySection | null {
  if (raw === 'structure' || raw === 'scan') return raw;
  return null;
}

export function DataQualityPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { t } = useI18n();
  const copy = t.data_quality.page;
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();
  const workspace = id ? getWorkspace(id) : undefined;
  const canEditGovernance = workspace ? ['owner', 'admin'].includes(workspace.my_role) : false;
  const scrolledRef = useRef(false);
  const [scanDialogOpen, setScanDialogOpen] = useState(false);

  if (!id) return null;

  const scrollTarget = parseScrollTarget(searchParams.get('tab'));
  const ontologyUriFromUrl = searchParams.get('ontology_uri')?.trim() || null;
  const canStructure = Boolean(caps?.graph_runtime && caps?.graph);
  const canScan = Boolean(caps?.review);

  useEffect(() => {
    if (scrollTarget === 'scan') {
      setScanDialogOpen(true);
      return;
    }
    if (scrollTarget !== 'structure' || scrolledRef.current) return;
    const el = document.getElementById('data-quality-structure');
    if (!el) return;
    scrolledRef.current = true;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [scrollTarget]);

  const headerActions = (
    <>
      {!capsLoading && canScan ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8"
          data-testid="data-quality-open-scan-settings"
          onClick={() => setScanDialogOpen(true)}
        >
          <PublicIcon name="settings-01" size={14} />
          {copy.open_scan_settings}
        </Button>
      ) : null}
      <Button type="button" size="sm" variant="outline" className="h-8" asChild>
        <Link to={workspaceOntologyHubPath(id, 'statement')}>
          <PublicIcon name="git-branch-01" size={14} />
          {copy.open_mappings}
        </Link>
      </Button>
      <Button type="button" size="sm" variant="outline" className="h-8" asChild>
        <Link to={workspaceReviewPath(id)}>
          <PublicIcon name="check-square-contained" size={14} />
          {copy.open_review}
        </Link>
      </Button>
    </>
  );

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.data_quality.menu.data_quality },
      ]}
      subtitle={copy.subtitle}
      meta={copy.structure_meta}
      actions={headerActions}
      className="min-h-0 overflow-hidden"
    >
      <div className="flex min-h-0 flex-1 flex-col" data-testid="data-quality-page">
        {!capsLoading && !canScan ? (
          <WorkspaceUnavailable workspaceId={id} feature="review" />
        ) : null}

        <Dialog open={scanDialogOpen} onOpenChange={setScanDialogOpen}>
          <DialogContent className="max-h-[min(90vh,44rem)] overflow-y-auto sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>{copy.tab_scan}</DialogTitle>
              <DialogDescription>{copy.section_scan_hint}</DialogDescription>
            </DialogHeader>
            {canScan ? (
              <GovernanceConfigPanel
                workspaceId={id}
                canEdit={canEditGovernance}
                showDataQualityLink={false}
              />
            ) : null}
          </DialogContent>
        </Dialog>

        <section
          id="data-quality-structure"
          className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border"
        >
          {!capsLoading && !canStructure ? (
            <div className="p-6">
              <WorkspaceUnavailable workspaceId={id} feature="sparql" />
            </div>
          ) : (
            <OntologyShaclPanel
              workspaceId={id}
              className="min-h-[min(58vh,680px)] min-h-0 flex-1 border-0"
              initialOntologyUri={ontologyUriFromUrl}
            />
          )}
        </section>
      </div>
    </ConsolePageLayout>
  );
}
