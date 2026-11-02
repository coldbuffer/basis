import { useEffect, useMemo, useRef } from 'react';
import { DataSet } from 'vis-data';
import { Timeline } from 'vis-timeline';
import type { TimelineOptions } from 'vis-timeline';
import 'vis-timeline/styles/vis-timeline-graph2d.css';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { cn } from '@/lib/utils.js';
import { clampMs, msToIso, parseInstantMs } from '@/modules/workspace/graph/lib/temporal/instant.js';
import { resolveScrubberBounds } from '@/modules/workspace/graph/lib/temporal/scrubber-bounds.js';
import { buildTimelineAxisFormat } from '@/modules/workspace/graph/lib/temporal/timeline-axis-format.js';
import { buildVisTimelineConsoleStyles } from '@/modules/workspace/graph/lib/temporal/vis-timeline-console-styles.js';

const FROM_MARKER_ID = 'range-from';
const TO_MARKER_ID = 'range-to';
const WRAP_CLASS = 'basis-temporal-range-timeline';
const ONE_DAY_MS = 1000 * 60 * 60 * 24;
const MIN_AXIS_SPAN_MS = 1;

const TIMELINE_CSS = buildVisTimelineConsoleStyles({
  wrapClass: WRAP_CLASS,
  markers: [
    {
      id: FROM_MARKER_ID,
      line: 'color-mix(in oklch, var(--primary) 35%, transparent)',
      marker: 'var(--primary)',
    },
    {
      id: TO_MARKER_ID,
      line: 'color-mix(in oklch, var(--info) 35%, transparent)',
      marker: 'var(--info)',
    },
  ],
});

export function TemporalRangeTimeline({
  ledgerMin,
  ledgerMax,
  fromIso,
  toIso,
  onFromIsoChange,
  onToIsoChange,
  disabled = false,
  className,
}: {
  ledgerMin?: string;
  ledgerMax?: string;
  fromIso: string;
  toIso: string;
  onFromIsoChange: (iso: string) => void;
  onToIsoChange: (iso: string) => void;
  disabled?: boolean;
  className?: string;
}) {
  const { locale } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<Timeline | null>(null);
  const suppressEventsRef = useRef(false);
  const onFromRef = useRef(onFromIsoChange);
  const onToRef = useRef(onToIsoChange);
  onFromRef.current = onFromIsoChange;
  onToRef.current = onToIsoChange;

  const now = useMemo(() => new Date(), []);

  const { minBound, maxBound } = useMemo(
    () => resolveScrubberBounds({ minDate: ledgerMin, maxDate: ledgerMax, now }),
    [ledgerMax, ledgerMin, now],
  );

  const minMs = minBound.getTime();
  const rawMaxMs = maxBound.getTime();
  const maxMs = rawMaxMs > minMs ? rawMaxMs : minMs + MIN_AXIS_SPAN_MS;
  const spanMs = maxMs - minMs;
  const timelineMax = useMemo(() => new Date(maxMs), [maxMs]);

  const axisFormat = useMemo(
    () => buildTimelineAxisFormat(locale as Locale),
    [locale],
  );

  const fromDate = useMemo(() => {
    const parsed = parseInstantMs(fromIso);
    return new Date(clampMs(parsed ?? minMs, minMs, maxMs));
  }, [fromIso, maxMs, minMs]);

  const toDate = useMemo(() => {
    const parsed = parseInstantMs(toIso);
    return new Date(clampMs(parsed ?? maxMs, minMs, maxMs));
  }, [maxMs, minMs, toIso]);

  useEffect(() => {
    if (!containerRef.current) return;

    const items = new DataSet([]);
    const zoomMin = Math.min(ONE_DAY_MS, Math.max(1, Math.floor(spanMs / 24)));
    const zoomMax = Math.max(spanMs * 4, ONE_DAY_MS * 365 * 5);

    const options: TimelineOptions = {
      height: '96px',
      min: minBound,
      max: timelineMax,
      start: minBound,
      end: timelineMax,
      showCurrentTime: false,
      zoomable: true,
      moveable: true,
      zoomMin,
      zoomMax,
      showMajorLabels: true,
      showMinorLabels: true,
      orientation: { axis: 'bottom' },
      margin: { item: 0, axis: 0 },
      selectable: false,
      stack: false,
      format: axisFormat,
    } as TimelineOptions;

    const timeline = new Timeline(containerRef.current, items, options);
    timelineRef.current = timeline;
    timeline.addCustomTime(fromDate, FROM_MARKER_ID);
    timeline.addCustomTime(toDate, TO_MARKER_ID);

    timeline.on('timechange', (props: { id: string; time: Date }) => {
      if (suppressEventsRef.current) return;
      const iso = msToIso(props.time.getTime());
      if (props.id === FROM_MARKER_ID) {
        onFromRef.current(iso);
      } else if (props.id === TO_MARKER_ID) {
        onToRef.current(iso);
      }
    });

    return () => {
      timeline.destroy();
      timelineRef.current = null;
    };
  }, []);

  useEffect(() => {
    const timeline = timelineRef.current;
    if (!timeline) return;

    const zoomMin = Math.min(ONE_DAY_MS, Math.max(1, Math.floor(spanMs / 24)));
    const zoomMax = Math.max(spanMs * 4, ONE_DAY_MS * 365 * 5);

    timeline.setOptions({
      min: minBound,
      max: timelineMax,
      start: minBound,
      end: timelineMax,
      zoomMin,
      zoomMax,
      format: axisFormat,
    });
  }, [axisFormat, minBound, spanMs, timelineMax]);

  useEffect(() => {
    const timeline = timelineRef.current;
    if (!timeline) return;
    suppressEventsRef.current = true;
    timeline.setCustomTime(fromDate, FROM_MARKER_ID);
    timeline.setCustomTime(toDate, TO_MARKER_ID);
    suppressEventsRef.current = false;
  }, [fromDate, toDate]);

  return (
    <div
      className={cn(
        WRAP_CLASS,
        'overflow-hidden rounded-lg border border-border bg-muted/20 px-2 pt-2',
        disabled && 'pointer-events-none opacity-60',
        className,
      )}
    >
      <style>{TIMELINE_CSS}</style>
      <div ref={containerRef} className="min-h-[96px] w-full" />
    </div>
  );
}
