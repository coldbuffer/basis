import type { LocaleMessages } from '@/i18n/en.js';

type McpIntegrationCopy = LocaleMessages['integration']['mcp'];

export function mcpTokenScopeLabel(copy: McpIntegrationCopy, scope: string): string {
  const labels = copy.scope_labels as Record<string, string>;
  return labels[scope] ?? labels[scope.toLowerCase()] ?? scope;
}
