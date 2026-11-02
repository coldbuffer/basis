import type { LocaleMessages } from '@/i18n/en.js';
import type { Locale } from '@/i18n/locale.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import { workspaceMemberRoleLabel } from '@/modules/workspace/settings/lib/settings-labels.js';

export function formatBasisAuditModelKind(locale: Locale, kind: string): string {
  const models = messagesForLocale(locale).admin_models.page;
  if (kind === 'llm') return models.tab_llm;
  if (kind === 'embed') return models.tab_embed;
  return kind;
}

export function formatBasisAuditMemberRole(locale: Locale, role: string): string {
  const ks = messagesForLocale(locale).settings.panel;
  return workspaceMemberRoleLabel(ks, role);
}
