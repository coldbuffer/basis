import { PlatformConnectorAdmin } from '@/modules/admin/connectors/components/platform-connector-admin.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { useI18n } from '@/i18n/context.js';
import { usePlatformAdminCrumbs } from '@/lib/admin/use-platform-admin-crumbs.js';

export function AdminConnectorsPage() {
  const { t } = useI18n();
  const ps = t.admin_settings.page.connectors;
  const crumbs = usePlatformAdminCrumbs(t.core.workspace_nav.platform.connectors);

  return (
    <ConsolePageLayout
      crumbs={crumbs}
      subtitle={ps.section_lead}
    >
      <PlatformConnectorAdmin />
    </ConsolePageLayout>
  );
}
