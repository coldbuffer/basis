import type { Locale } from './locale.js';
import { LOCALE_HTML_LANG } from './locale.js';
import { messagesForLocale } from './pick-locale.js';

export function fmt(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(vars[key] ?? `{${key}}`));
}

/** English uses distinct singular copy when count === 1; other locales typically share one template. */
export function pickCountForm<T extends string>(
  locale: Locale,
  count: number,
  one: T,
  many: T,
): T {
  return locale === 'en' && count === 1 ? one : many;
}

export function requestFailedStatusMessage(locale: Locale, status: number): string {
  return fmt(messagesForLocale(locale).core.common.requestFailedStatus, { status });
}

export function formatLocaleNumber(locale: Locale, value: number | null | undefined): string {
  const safe = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  return safe.toLocaleString(LOCALE_HTML_LANG[locale]);
}

export function formatLocaleFixedDecimals(
  locale: Locale,
  value: number | null | undefined,
  fractionDigits: number,
): string {
  const safe = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  return safe.toLocaleString(LOCALE_HTML_LANG[locale], {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

/** `ratio` is 0–1; appends a literal % (not localized per Intl percent style). */
export function formatLocalePercent(
  locale: Locale,
  ratio: number,
  fractionDigits = 1,
): string {
  return `${formatLocaleFixedDecimals(locale, ratio * 100, fractionDigits)}%`;
}

const ISO_WITHOUT_TZ_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

function parseDateValue(value: Date | string | number): Date {
  if (value instanceof Date) return value;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (ISO_WITHOUT_TZ_RE.test(trimmed)) {
      return new Date(`${trimmed}Z`);
    }
    return new Date(trimmed);
  }
  return new Date(value);
}

export function formatLocaleDateTime(
  locale: Locale,
  value: Date | string | number,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = parseDateValue(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleString(LOCALE_HTML_LANG[locale], options);
}

/** Compact notification badge: localized number, or "{cap}+" when over the display cap. */
export function formatBadgeCount(locale: Locale, count: number, maxBeforeOverflow: number): string {
  if (count <= maxBeforeOverflow) {
    return formatLocaleNumber(locale, count);
  }
  const cap = formatLocaleNumber(locale, maxBeforeOverflow);
  return fmt(messagesForLocale(locale).core.common.badgeOverflow, { cap });
}

export function compareLocaleStrings(locale: Locale, a: string, b: string): number {
  return a.localeCompare(b, LOCALE_HTML_LANG[locale]);
}

/** Compact year/month label for graph temporal scrubber (locale-aware ordering). */
export function formatLocaleYearMonth(locale: Locale, value: Date): string {
  return formatLocaleDateTime(locale, value, { year: 'numeric', month: '2-digit' });
}
