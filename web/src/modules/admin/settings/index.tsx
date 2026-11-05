import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { PlatformAccessSettings } from '@/modules/admin/settings/components/platform-access-settings.js';
import { PlatformOrgSsoSection } from '@/modules/admin/settings/components/platform-org-sso-section.js';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { basisIsDesktopProduct } from '@/lib/runtime/basis-runtime.js';
import { usePlatformAdminCrumbs } from '@/lib/admin/use-platform-admin-crumbs.js';
import { cn } from '@/lib/utils.js';

type SettingsTab = 'access' | 'oidc' | 'saml' | 'cas';

function resolveSettingsTab(raw: string | null, showAccess: boolean): SettingsTab {
  if (raw === 'oidc' || raw === 'saml' || raw === 'cas') return raw;
  if (raw === 'access' && showAccess) return 'access';
  return showAccess ? 'access' : 'oidc';
}

export function SettingsPage() {
  const { t } = useI18n();
  const ps = t.admin_settings.page;
  const { isAdmin } = useBasisSession();
  const desktopProduct = basisIsDesktopProduct();
  const showAccess = !desktopProduct && isAdmin;
  const showSso = !desktopProduct;
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = resolveSettingsTab(searchParams.get('tab'), showAccess);
  const protocol = tab === 'oidc' || tab === 'saml' || tab === 'cas' ? tab : 'oidc';
  const [siteUrl, setSiteUrl] = useState('');
  const crumbs = usePlatformAdminCrumbs(t.admin_settings.page.nav_title);
  const subtitle = desktopProduct ? undefined : showAccess ? ps.nav_subtitle : ps.org_sso_section_lead;

  return (
    <ConsolePageLayout crumbs={crumbs} subtitle={subtitle}>
      <div className="mx-auto w-full max-w-3xl pb-4">
        {desktopProduct ? (
          <p className="text-sm leading-relaxed text-muted-foreground">{ps.desktop_settings_lead}</p>
        ) : (
          <>
            <Tabs
              value={tab}
              onValueChange={(value) => {
                setSearchParams({ tab: value }, { replace: true });
              }}
            >
              <TabsList>
                {showAccess ? <TabsTrigger value="access">{ps.tab_access}</TabsTrigger> : null}
                {showSso ? (
                  <>
                    <TabsTrigger value="oidc">{ps.tab_oidc}</TabsTrigger>
                    <TabsTrigger value="saml">{ps.tab_saml}</TabsTrigger>
                    <TabsTrigger value="cas">{ps.tab_cas}</TabsTrigger>
                  </>
                ) : null}
              </TabsList>
              {showAccess ? (
                <TabsContent value="access" forceMount className="mt-4 data-[state=inactive]:hidden">
                  <PlatformAccessSettings onSiteUrlChange={setSiteUrl} />
                </TabsContent>
              ) : null}
            </Tabs>
            {showSso ? (
              <div className={cn('mt-4', tab === 'access' && 'hidden')}>
                <PlatformOrgSsoSection siteBaseUrl={siteUrl} protocol={protocol} />
              </div>
            ) : null}
          </>
        )}
      </div>
    </ConsolePageLayout>
  );
}
