import { formatLocaleDateTime, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import type { TimelineFormatOption, TimelineTimeAxisScaleType } from 'vis-timeline';

type AxisLabelInput = Date | { toDate?: () => Date };

function axisDate(value: AxisLabelInput): Date {
  if (value instanceof Date) return value;
  if (typeof value.toDate === 'function') return value.toDate();
  return new Date(Number.NaN);
}

function formatMinorLabel(locale: Locale, date: Date, scale: TimelineTimeAxisScaleType): string {
  switch (scale) {
    case 'millisecond':
      return formatLocaleDateTime(locale, date, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3,
      });
    case 'second':
      return formatLocaleDateTime(locale, date, { second: 'numeric' });
    case 'minute':
    case 'hour':
      return formatLocaleDateTime(locale, date, { hour: '2-digit', minute: '2-digit' });
    case 'weekday':
      return formatLocaleDateTime(locale, date, { weekday: 'short', day: 'numeric' });
    case 'day':
      return formatLocaleDateTime(locale, date, { day: 'numeric' });
    case 'week':
      if (date.getDate() === 1 && date.getDay() !== 0) {
        return '';
      }
      return formatLocaleNumber(locale, getWeekNumber(date));
    case 'month':
      return formatLocaleDateTime(locale, date, { month: 'short' });
    case 'year':
      return formatLocaleDateTime(locale, date, { year: 'numeric' });
    default:
      return formatLocaleDateTime(locale, date);
  }
}

function formatMajorLabel(locale: Locale, date: Date, scale: TimelineTimeAxisScaleType): string {
  switch (scale) {
    case 'millisecond':
      return formatLocaleDateTime(locale, date, {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    case 'second':
      return formatLocaleDateTime(locale, date, {
        day: 'numeric',
        month: 'long',
        hour: '2-digit',
        minute: '2-digit',
      });
    case 'minute':
    case 'hour':
      return formatLocaleDateTime(locale, date, {
        weekday: 'short',
        day: 'numeric',
        month: 'long',
      });
    case 'weekday':
    case 'day':
    case 'week':
      return formatLocaleDateTime(locale, date, { month: 'long', year: 'numeric' });
    case 'month':
      return formatLocaleDateTime(locale, date, { year: 'numeric' });
    case 'year':
      return '';
    default:
      return formatLocaleDateTime(locale, date);
  }
}

/** ISO week number (Monday-based), aligned with vis-timeline's default week ticks. */
function getWeekNumber(date: Date): number {
  const utc = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const day = utc.getUTCDay() || 7;
  utc.setUTCDate(utc.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1));
  return Math.ceil(((utc.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

export function buildTimelineAxisFormat(locale: Locale): TimelineFormatOption {
  return {
    minorLabels: (date, scale) => {
      const native = axisDate(date);
      if (Number.isNaN(native.getTime())) return '';
      return formatMinorLabel(locale, native, scale as TimelineTimeAxisScaleType);
    },
    majorLabels: (date, scale) => {
      const native = axisDate(date);
      if (Number.isNaN(native.getTime())) return '';
      return formatMajorLabel(locale, native, scale as TimelineTimeAxisScaleType);
    },
  };
}
