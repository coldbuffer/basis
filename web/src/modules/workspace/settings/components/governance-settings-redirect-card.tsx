import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button.js';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.js';
import { useI18n } from '@/i18n/context.js';
import { workspaceQualityPath } from '@/lib/nav/nav-config.js';

export function GovernanceSettingsRedirectCard({ workspaceId }: { workspaceId: string }) {
  const { t } = useI18n();
  const g = t.settings.panel.governance;

  return (
    <Card data-testid="settings-governance-redirect-card">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base">{g.title}</CardTitle>
          <CardDescription className="mt-1">{g.settings_redirect_body}</CardDescription>
        </div>
        <Button type="button" size="sm" variant="outline" asChild>
          <Link to={workspaceQualityPath(workspaceId, 'scan')}>{g.settings_redirect_button}</Link>
        </Button>
      </CardHeader>
    </Card>
  );
}
