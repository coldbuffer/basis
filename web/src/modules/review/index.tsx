import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Suspense } from 'react';
import { ConsolePageLayout } from '@/components/app/shared/console/index.js';
import { GovernanceWorkspaceShell } from '@/components/app/shared/workspace/frame/governance-ws-shell.js';
import { WorkspaceUnavailable } from '@/components/app/shared/workspace/frame/ws-unavailable.js';
import { ReviewQueuePanel } from './components/review-queue-panel.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useWorkspaceCapabilities } from '@/lib/workspace/capabilities.js';
import { useI18n } from '@/i18n/context.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { workspacePath } from '@/lib/nav/nav-config.js';
import {
  activityLogBrowseDecisionsPath,
  parseReviewUrlState,
} from '@/modules/review/lib/review-url-state.js';

export function ReviewPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { t } = useI18n();
  const { getWorkspace } = useWorkspaceCatalog();
  const { caps, loading: capsLoading } = useWorkspaceCapabilities();
  const reviewUrl = parseReviewUrlState(searchParams.toString());
  const reviewFocusItemId = reviewUrl.reviewItemId?.trim() || '';

  if (!id) {
    return null;
  }

  const reviewBody =
    !capsLoading && caps && !caps.review ? (
      <WorkspaceUnavailable workspaceId={id} feature="review" />
    ) : (
      <GovernanceWorkspaceShell workspaceId={id} className="min-h-0 flex-1">
        <Suspense
          fallback={
            <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              {t.review.page.loading}
            </div>
          }
        >
          <ReviewQueuePanel workspaceId={id} focusItemId={reviewFocusItemId || undefined} />
        </Suspense>
      </GovernanceWorkspaceShell>
    );

  return (
    <ConsolePageLayout
      crumbs={[
        { label: t.core.workspace_nav.platform.workspaces, to: '/workspaces' },
        { label: getWorkspace(id)?.name ?? id, to: workspacePath(id, 'graph') },
        { label: t.review.menu.review },
      ]}
      subtitle={
        <>
          {t.review.page.subtitle}{' '}
          <Link
            to={activityLogBrowseDecisionsPath(id)}
            className="text-primary underline-offset-2 hover:underline"
            data-testid="review-open-activity-log"
          >
            {t.review.page.link_activity_log}
          </Link>
        </>
      }
      className="min-h-0 overflow-hidden"
    >
      {reviewBody}
    </ConsolePageLayout>
  );
}
