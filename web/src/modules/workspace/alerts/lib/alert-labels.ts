import { fmt } from '@/i18n/format.js';
import type { LocaleMessages } from '@/i18n/en.js';

type AlertsCopy = LocaleMessages['alerts']['page'];

export function alertKindLabel(alerts: AlertsCopy, kind: string): string {
  const labels = alerts.kind_labels as Record<string, string>;
  if (labels[kind]) return labels[kind];
  if (kind.startsWith('llm.')) {
    const code = kind.slice(4);
    return fmt(alerts.kind_llm_fallback, { code });
  }
  return kind;
}

export function alertSeverityLabel(alerts: AlertsCopy, severity: string): string {
  const normalized = severity.toLowerCase();
  if (normalized === 'critical' || normalized === 'error' || normalized === 'high') {
    return alerts.severity_critical;
  }
  if (normalized === 'warning' || normalized === 'warn' || normalized === 'medium') {
    return alerts.severity_warning;
  }
  return alerts.severity_info;
}
