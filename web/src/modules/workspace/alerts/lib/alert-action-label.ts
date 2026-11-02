import type { LocaleMessages } from '@/i18n/en.js';
import type { AlertActionLabelKey } from '@/modules/workspace/alerts/lib/alert-actions.js';

const LABEL_KEYS: Record<
  AlertActionLabelKey,
  keyof LocaleMessages['alerts']['page'] & string
> = {
  viewProposal: 'view_proposal',
  viewSources: 'view_sources',
  viewReview: 'view_review',
  viewSettings: 'view_settings',
  viewDecisions: 'view_decisions',
  viewProcessingJob: 'view_processing_job',
};

export function alertActionLabel(
  alertsPage: LocaleMessages['alerts']['page'],
  labelKey: AlertActionLabelKey,
): string {
  const key = LABEL_KEYS[labelKey];
  return alertsPage[key] as string;
}
