import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { useCallback, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import {
  OntologyAlignmentsPanel,
  OntologyRegistryPanel,
  OntologyVersionsPanel,
  type OntologyHubPageActions,
} from '@/modules/ontology/components/ontology-hub-panels.js';
import { Button } from '@/components/ui/button.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import type { OntologyHubTab } from '@/modules/analyze/lib/hub-route.js';
import { ontologyHubTabEnabled, resolveOntologyHubTab } from '@/modules/analyze/lib/hub-tabs.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

const WORKSPACE_CLASS = 'min-h-0 flex-1 rounded-lg border border-border';
const INTERIOR_WORKSPACE_CLASS = 'h-[calc(100svh-14rem)] min-h-[28rem] flex-1 rounded-lg border border-border';

export function OntologyPage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps } = useWorkspaceCapabilities();
  const [pageActions, setPageActions] = useState<OntologyHubPageActions | null>(null);
  const onPageActionsChange = useCallback((actions: OntologyHubPageActions | null) => {
    setPageActions(actions);
  }, []);

  const rawTabParam = searchParams.get('tab');

  const tab = useMemo(
    () =>
      resolveOntologyHubTab(
        rawTabParam,
        searchParams.has('ontologyProposal'),
        searchParams.has('ontologyEntity'),
        caps,
      ),
    [caps, rawTabParam, searchParams],
  );

  if (!id) {
    return null;
  }

  const kbName = getWorkspace(id)?.name ?? id;
  const hubTabs = t.ontology.hub.hub_tabs;
  const hubSubtitles = t.ontology.hub.hub_subtitles;

  function onTabChange(value: string) {
    const next = value as OntologyHubTab;
    const params = new URLSearchParams(searchParams);
    if (next === 'registry') {
      params.delete('tab');
    } else {
      params.set('tab', next);
    }
    setSearchParams(params, { replace: true });
  }

  const onFixInEditor = useCallback(
    (entityUri: string) => {
      const params = new URLSearchParams(searchParams);
      params.set('tab', 'editor');
      params.set('ontologyEntity', entityUri);
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: kbName, to: workspacePath(id, 'graph') },
        { label: t.ontology.menu.ontology },
      ]}
      subtitle={hubSubtitles[tab]}
      actions={
        tab === 'registry' && pageActions ? (
          <Button type="button" size="sm" onClick={pageActions.openLoadOntology}>
            <PublicIcon name="plus-01" size={14} />
            {t.ontology.page.load_ontology}
          </Button>
        ) : undefined
      }
      className="min-h-0 flex-1 overflow-hidden"
    >
      <Tabs value={tab} onValueChange={onTabChange} className="flex min-h-0 flex-1 flex-col">
        <TabsList className="h-auto flex-wrap">
          <TabsTrigger value="registry" disabled={!ontologyHubTabEnabled('registry', caps)}>
            {hubTabs.registry}
          </TabsTrigger>
          <TabsTrigger value="editor" disabled={!ontologyHubTabEnabled('editor', caps)}>
            {hubTabs.editor}
          </TabsTrigger>
          <TabsTrigger value="health" disabled={!ontologyHubTabEnabled('health', caps)}>
            {hubTabs.health}
          </TabsTrigger>
          <TabsTrigger value="versions" disabled={!ontologyHubTabEnabled('versions', caps)}>
            {hubTabs.versions}
          </TabsTrigger>
          <TabsTrigger value="alignments" disabled={!ontologyHubTabEnabled('alignments', caps)}>
            {hubTabs.alignments}
          </TabsTrigger>
        </TabsList>

        <TabsContent
          value="registry"
          className="mt-4 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
        >
          <OntologyRegistryPanel
            workspaceId={id}
            panel="registry"
            className={INTERIOR_WORKSPACE_CLASS}
            onPageActionsChange={onPageActionsChange}
          />
        </TabsContent>
        <TabsContent
          value="editor"
          className="mt-4 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
        >
          <OntologyRegistryPanel workspaceId={id} panel="editor" className={INTERIOR_WORKSPACE_CLASS} />
        </TabsContent>
        <TabsContent
          value="health"
          className="mt-4 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
        >
          <OntologyRegistryPanel
            workspaceId={id}
            panel="health"
            className={INTERIOR_WORKSPACE_CLASS}
            onFixInEditor={onFixInEditor}
          />
        </TabsContent>
        <TabsContent
          value="versions"
          className="mt-4 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
        >
          <OntologyVersionsPanel workspaceId={id} className={WORKSPACE_CLASS} />
        </TabsContent>
        <TabsContent
          value="alignments"
          className="mt-4 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
        >
          <OntologyAlignmentsPanel workspaceId={id} className="min-h-0 flex-1" />
        </TabsContent>
      </Tabs>
    </ConsolePageLayout>
  );
}
