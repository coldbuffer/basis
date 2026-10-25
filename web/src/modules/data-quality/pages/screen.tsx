import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { GovernanceConfigPanel } from '@/modules/settings/components/governance-config-panel.js';
import { OntologyShaclPanel } from '@/modules/ontology/components/ontology-hub-panels.js';
import { Button } from '@/components/ui/button.js';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath, workspaceQualityPath, workspaceReviewPath } from '@/lib/nav/nav-config.js';

type QualityTab = 'overview' | 'structure' | 'scan';

function parseQualityTab(raw: string | null): QualityTab {
  if (raw === 'structure' || raw === 'scan') return raw;
  return 'overview';
}

export function DataQualityPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useI18n();
  const copy = t.data_quality.page;
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();
  const workspace = id ? getWorkspace(id) : undefined;
  const canEditGovernance = workspace ? ['owner', 'admin'].includes(workspace.my_role) : false;

  if (!id) return null;

  const tab = parseQualityTab(searchParams.get('tab'));
  const ontologyUriFromUrl = searchParams.get('ontology_uri')?.trim() || null;
  const canStructure = Boolean(caps?.graph_runtime && caps?.graph);
  const canScan = Boolean(caps?.review);

  function onTabChange(value: string) {
    const next = new URLSearchParams(searchParams);
    if (value === 'overview') next.delete('tab');
    else next.set('tab', value);
    setSearchParams(next, { replace: true });
  }

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.data_quality.menu.data_quality },
      ]}
      subtitle={copy.subtitle}
      className="min-h-0 overflow-hidden"
    >
      <Tabs value={tab} onValueChange={onTabChange} className="flex min-h-0 flex-1 flex-col gap-4">
        <TabsList className="h-auto w-full flex-wrap justify-start" data-testid="data-quality-tabs">
          <TabsTrigger value="overview">{copy.tab_overview}</TabsTrigger>
          <TabsTrigger value="structure" disabled={!canStructure}>{copy.tab_structure}</TabsTrigger>
          <TabsTrigger value="scan" disabled={!canScan}>{copy.tab_scan}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-0 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{copy.overview_structure_title}</CardTitle>
              <CardDescription>{copy.overview_structure_body}</CardDescription>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{copy.overview_mappings_title}</CardTitle>
              <CardDescription>{copy.overview_mappings_body}</CardDescription>
            </CardHeader>
          </Card>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to={workspaceQualityPath(id, 'structure')}>{copy.tab_structure}</Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link to={workspacePath(id, 'mappings')}>{copy.open_mappings}</Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link to={workspaceReviewPath(id)}>{copy.open_review}</Link>
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="structure" className="mt-0 flex min-h-0 flex-1 flex-col overflow-hidden">
          {!capsLoading && !canStructure ? (
            <WorkspaceUnavailable workspaceId={id} feature="sparql" />
          ) : (
            <div className="flex min-h-[28rem] flex-1 flex-col overflow-hidden rounded-lg border border-border">
              <OntologyShaclPanel
                workspaceId={id}
                className="min-h-0 flex-1 border-0"
                initialOntologyUri={ontologyUriFromUrl}
              />
            </div>
          )}
        </TabsContent>

        <TabsContent value="scan" className="mt-0 space-y-4">
          {!capsLoading && !canScan ? (
            <WorkspaceUnavailable workspaceId={id} feature="review" />
          ) : (
            <GovernanceConfigPanel workspaceId={id} canEdit={canEditGovernance} />
          )}
        </TabsContent>
      </Tabs>
    </ConsolePageLayout>
  );
}
