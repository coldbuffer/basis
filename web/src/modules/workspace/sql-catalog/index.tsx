import { useParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { SqlCatalogPanel } from '@/modules/workspace/sql-catalog/components/sql-catalog-panel.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

export function SqlCatalogPage() {
  const { id } = useParams();
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();

  if (!id) return null;

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.sql_catalog.menu.sql_catalog },
      ]}
      subtitle={t.sql_catalog.page.subtitle}
    >
      <SqlCatalogPanel workspaceId={id} />
    </ConsolePageLayout>
  );
}
