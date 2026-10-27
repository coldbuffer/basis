import { Link } from 'react-router-dom';
import {
  proposalIdFromGraphAuditDetail,
  reviewItemIdFromGraphAuditDetail,
} from '@/modules/graph/lib/graph-audit.js';
import { useI18n } from '@/i18n/context.js';
import { workspaceOntologyProposalPath } from '@/lib/nav/nav-config.js';
import {
  decisionIdFromDetail,
  reviewDecisionPath,
  reviewItemPath,
} from '@/modules/review/lib/review-url-state.js';

const linkClass =
  'inline-block text-[11px] text-foreground underline-offset-2 hover:underline';

export function GraphAuditEventLinks({
  workspaceId,
  detail,
  testIdPrefix = 'graph-audit',
}: {
  workspaceId: string;
  detail?: Record<string, unknown>;
  testIdPrefix?: string;
}) {
  const { t } = useI18n();
  const reviewItemId = reviewItemIdFromGraphAuditDetail(detail);
  const decisionId = decisionIdFromDetail(detail);
  const proposalId = proposalIdFromGraphAuditDetail(detail);

  if (!reviewItemId && !decisionId && !proposalId) return null;

  return (
    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
      {reviewItemId ? (
        <Link
          to={reviewItemPath(workspaceId, reviewItemId)}
          className={linkClass}
          data-testid={`${testIdPrefix}-review-${reviewItemId}`}
        >
          {t.review.queue.open_review_item}
        </Link>
      ) : null}
      {decisionId ? (
        <Link
          to={reviewDecisionPath(workspaceId, decisionId)}
          className={linkClass}
          data-testid={`${testIdPrefix}-decision-${decisionId}`}
        >
          {t.review.queue.open_decision}
        </Link>
      ) : null}
      {proposalId ? (
        <Link
          to={workspaceOntologyProposalPath(workspaceId, proposalId)}
          className={linkClass}
          data-testid={`${testIdPrefix}-proposal-${proposalId}`}
        >
          {t.review.queue.open_ontology_proposal}
        </Link>
      ) : null}
    </div>
  );
}
