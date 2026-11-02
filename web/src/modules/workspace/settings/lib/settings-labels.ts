import type { AnyLocaleMessages } from '@/i18n/pick-locale.js';

type SettingsPanelCopy = AnyLocaleMessages['settings']['panel'];

export function workspaceMemberRoleLabel(ks: SettingsPanelCopy, role: string): string {
  const labels = ks.role_labels as Record<string, string>;
  return labels[role] ?? role;
}

export function workspaceVisibilityLabel(ks: SettingsPanelCopy, visibility: string): string {
  const labels = ks.visibility_labels as Record<string, string>;
  return labels[visibility] ?? visibility;
}
