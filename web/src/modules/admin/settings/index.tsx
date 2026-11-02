import type { ReactNode } from 'react';
import { useState } from 'react';
import { PlatformAccessSettings } from '@/modules/admin/settings/components/platform-access-settings.js';
import { PlatformOrgSsoSection } from '@/modules/admin/settings/components/platform-org-sso-section.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { useI18n } from '@/i18n/context.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { basisIsDesktopProduct } from '@/lib/runtime/basis-runtime.js';
import { usePlatformAdminCrumbs } from '@/lib/admin/use-platform-admin-crumbs.js';

function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-4">
      <header className="space-y-1">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {description ? (
          <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        ) : null}
      </header>
      {children}
    </section>
  );
}

export function SettingsPage() {
  const { t } = useI18n();
  const ps = t.admin_settings.page;
  const { isAdmin } = useBasisSession();
  const desktopProduct = basisIsDesktopProduct();
  const [siteUrl, setSiteUrl] = useState('');
  const crumbs = usePlatformAdminCrumbs(t.admin_settings.page.nav_title);

  return (
    <ConsolePageLayout crumbs={crumbs} subtitle={t.admin_settings.page.nav_subtitle}>
      <div className="mx-auto w-full max-w-3xl space-y-12 pb-4">
        {desktopProduct ? (
          <p className="text-sm leading-relaxed text-muted-foreground">{ps.desktop_settings_lead}</p>
        ) : null}
        {!desktopProduct && isAdmin ? (
          <SettingsSection title={ps.tab_access} description={ps.access.page_lead}>
            <PlatformAccessSettings onSiteUrlChange={setSiteUrl} />
          </SettingsSection>
        ) : null}

        {!desktopProduct ? (
          <SettingsSection title={ps.tab_org_sso} description={ps.org_sso_section_lead}>
            <PlatformOrgSsoSection siteBaseUrl={siteUrl} />
          </SettingsSection>
        ) : null}
      </div>
    </ConsolePageLayout>
  );
}
