import { useParams, useSearchParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { DerivedFactsPanel } from '@/modules/entities/components/derived-facts-panel.js';
import { LedgerEntityBrowser } from '@/components/app/shared/workspace/ledger-entity-browser.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { parseEntitiesUrlState } from '@/modules/entities/lib/entities-url-state.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

export function EntitiesPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { statementId: focusStatementId } = parseEntitiesUrlState(searchParams.toString());
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  if (!id) return null;

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.entities.menu.entities },
      ]}
      subtitle={t.entities.page.subtitle}
      className="min-h-0 overflow-hidden"
    >
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-auto min-[960px]:grid-cols-[minmax(0,1fr)_minmax(17.5rem,24rem)] min-[960px]:overflow-hidden">
        <div className="min-h-0 min-w-0 min-[960px]:overflow-auto">
          <LedgerEntityBrowser workspaceId={id} focusStatementId={focusStatementId} />
        </div>
        <DerivedFactsPanel workspaceId={id} />
      </div>
    </ConsolePageLayout>
  );
}
