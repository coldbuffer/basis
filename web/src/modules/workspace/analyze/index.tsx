import { useMemo } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import {
  AnalyzeReasoningPanel,
  AnalyzeSparqlPanel,
} from '@/modules/workspace/analyze/pages/analyze-panels.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import type { AnalyzeHubTab } from '@/modules/workspace/analyze/lib/hub-route.js';
import { analyzeHubTabEnabled, resolveAnalyzeHubTab } from '@/modules/workspace/analyze/lib/hub-tabs.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

const WORKSPACE_CLASS = 'min-h-0 flex-1 rounded-lg border border-border';

export function AnalyzePage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps } = useWorkspaceCapabilities();

  const tab = useMemo(
    () => resolveAnalyzeHubTab(searchParams.get('tab'), caps),
    [caps, searchParams],
  );

  if (!id) {
    return null;
  }

  const kbName = getWorkspace(id)?.name ?? id;
  const hubTabs = t.analyze.hub.hub_tabs;
  const integrationOpenApiPath = `${workspacePath(id, 'integration')}?tab=openapi`;

  function onTabChange(value: string) {
    const next = value as AnalyzeHubTab;
    const params = new URLSearchParams(searchParams);
    if (next === 'sparql') {
      params.delete('tab');
    } else {
      params.set('tab', next);
    }
    setSearchParams(params, { replace: true });
  }

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: kbName, to: workspacePath(id, 'graph') },
        { label: t.analyze.menu.analyze },
      ]}
      subtitle={
        <div className="space-y-1">
          <p>{t.analyze.page.subtitle}</p>
          <p className="text-xs text-muted-foreground">
            <Link to={integrationOpenApiPath} className="text-foreground underline-offset-2 hover:underline">
              {t.analyze.hub.integration_hint}
            </Link>
          </p>
        </div>
      }
      className="min-h-0 flex-1 overflow-hidden"
    >
      <Tabs value={tab} onValueChange={onTabChange} className="flex min-h-0 flex-1 flex-col">
        <TabsList>
          <TabsTrigger value="sparql" disabled={!analyzeHubTabEnabled('sparql', caps)}>
            {hubTabs.sparql}
          </TabsTrigger>
          <TabsTrigger value="reasoning" disabled={!analyzeHubTabEnabled('reasoning', caps)}>
            {hubTabs.reasoning}
          </TabsTrigger>
        </TabsList>

        <TabsContent
          value="sparql"
          className="mt-4 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
        >
          <AnalyzeSparqlPanel workspaceId={id} className={WORKSPACE_CLASS} />
        </TabsContent>
        <TabsContent
          value="reasoning"
          className="mt-4 flex min-h-0 flex-1 flex-col data-[state=inactive]:hidden"
        >
          <AnalyzeReasoningPanel workspaceId={id} className={WORKSPACE_CLASS} />
        </TabsContent>
      </Tabs>
    </ConsolePageLayout>
  );
}
