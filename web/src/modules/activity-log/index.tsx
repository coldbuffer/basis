import { useParams } from 'react-router-dom';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import { ActivityLogPanel } from './components/activity-log-panel.js';

export function ActivityLogPage() {
  const { id } = useParams();
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();

  if (!id) {
    return null;
  }

  const kbName = getWorkspace(id)?.name ?? id;

  return (
    <div
      className="basis-activity-log-shell flex min-h-0 w-full flex-1 flex-col"
      data-workspace-id={id}
      data-testid="workspace-activity-log-view"
    >
      <ConsolePageLayout
          crumbs={[
            { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
            { label: kbName, to: workspacePath(id, 'graph') },
            { label: t.activity_log.menu.activity_log },
          ]}
          subtitle={
            <div className="space-y-1">
              <p>{t.activity_log.page.subtitle}</p>
              <p className="text-xs text-muted-foreground" data-testid="activity-log-limit-hint">
                {t.activity_log.page.fetch_limit_hint}
              </p>
            </div>
          }
          className="gap-6 [&>:last-child]:min-h-0 [&>:last-child]:flex-none"
        >
          {!capsLoading && caps && !caps.review ? (
            <WorkspaceUnavailable workspaceId={id} feature="review" />
          ) : (
            <ActivityLogPanel workspaceId={id} />
          )}
      </ConsolePageLayout>
    </div>
  );
}
