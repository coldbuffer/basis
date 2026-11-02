import { useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { GraphDiff } from '@/modules/workspace/graph/components/graph-diff-view.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

export function GraphDiffPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();

  if (!id) return null;

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.graph.menu.graph_diff },
      ]}
      subtitle={t.graph.page.subtitle}
      className="min-h-0 overflow-hidden"
    >
      <GraphDiff
        workspaceId={id}
        className="min-h-0 flex-1 overflow-y-auto"
        initialFrom={searchParams.get('from') ?? undefined}
        initialTo={searchParams.get('to') ?? undefined}
      />
    </ConsolePageLayout>
  );
}
