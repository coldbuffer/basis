import { useEffect, useMemo, useState } from 'react';
import { OrgSamlPanel } from './org-saml-panel.js';
import { OrgSsoPanel } from './org-sso-panel.js';
import { Label } from '@/components/ui/label.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { useI18n } from '@/i18n/context.js';
import { openApiGET } from '@/lib/openapi/client.js';
import { useBasisSession } from '@/lib/session/basis-session.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';

type OrgRow = {
  id: string;
  name: string;
  slug: string;
  my_org_role: string | null;
};

const ORG_ADMIN_ROLES = new Set(['owner', 'admin']);

export function PlatformOrgSsoSection({ siteBaseUrl }: { siteBaseUrl?: string }) {
  const { t } = useI18n();
  const ps = t.admin_settings.page;
  const { isAdmin } = useBasisSession();
  const apiError = useApiErrorMessage();
  const [orgs, setOrgs] = useState<OrgRow[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    openApiGET<{ organizations: OrgRow[] }>('/api/v1/orgs')
      .then((body) => {
        const manageable = isAdmin
          ? body.organizations
          : body.organizations.filter(
              (o) => o.my_org_role != null && ORG_ADMIN_ROLES.has(o.my_org_role),
            );
        setOrgs(manageable);
        if (manageable.length > 0) {
          setSelectedOrgId((current) =>
            current && manageable.some((o) => o.id === current) ? current : manageable[0].id,
          );
        }
      })
      .catch((err) => setError(apiError(err)))
      .finally(() => setLoading(false));
  }, [apiError, isAdmin]);

  const selectedOrg = useMemo(
    () => orgs.find((o) => o.id === selectedOrgId),
    [orgs, selectedOrgId],
  );

  if (loading) {
    return <p className="text-sm text-muted-foreground">{t.core.common.loading}</p>;
  }

  if (error) {
    return <p className="text-sm text-destructive">{error}</p>;
  }

  if (orgs.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {isAdmin ? ps.org_sso_empty_admin : ps.org_sso_empty}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {orgs.length > 1 ? (
        <div className="max-w-md space-y-2">
          <Label htmlFor="platform-org-picker">{ps.org_sso_picker_label}</Label>
          <Select value={selectedOrgId} onValueChange={setSelectedOrgId}>
            <SelectTrigger id="platform-org-picker">
              <SelectValue placeholder={ps.org_sso_picker_label} />
            </SelectTrigger>
            <SelectContent>
              {orgs.map((org) => (
                <SelectItem key={org.id} value={org.id}>
                  {org.name} ({org.slug})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : selectedOrg ? (
        <p className="text-sm text-muted-foreground">
          {ps.org_sso_single_org}: <span className="font-medium text-foreground">{selectedOrg.name}</span>
        </p>
      ) : null}
      <OrgSsoPanel organizationId={selectedOrgId || null} siteBaseUrl={siteBaseUrl} />
      <OrgSamlPanel organizationId={selectedOrgId || null} />
    </div>
  );
}
