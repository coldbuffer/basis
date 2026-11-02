import { parseInstantMs } from '@/modules/workspace/graph/lib/temporal/instant.js';

/** Calendar cell date (local timezone) from an ISO instant. */
export function calendarDateFromIso(iso: string): Date | undefined {
  const ms = parseInstantMs(iso);
  if (ms === null) return undefined;
  const d = new Date(ms);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Start of local calendar day as ISO (for graph `from`). */
export function startOfLocalDayIso(day: Date): string {
  const d = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 0, 0, 0, 0);
  return d.toISOString();
}

/** End of local calendar day as ISO (for graph `to`). */
export function endOfLocalDayIso(day: Date): string {
  const d = new Date(day.getFullYear(), day.getMonth(), day.getDate(), 23, 59, 59, 999);
  return d.toISOString();
}

export function startOfLocalDay(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate(), 0, 0, 0, 0);
}

export function endOfLocalDay(day: Date): Date {
  return new Date(day.getFullYear(), day.getMonth(), day.getDate(), 23, 59, 59, 999);
}
