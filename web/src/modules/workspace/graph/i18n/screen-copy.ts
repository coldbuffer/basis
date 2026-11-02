import { en } from "@/i18n/en.js";
import {
  fmt,
  formatLocaleDateTime,
  formatLocaleNumber,
  formatLocaleYearMonth,
  pickCountForm,
  requestFailedStatusMessage,
} from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";
import type { GraphZoomTier } from "@/lib/workspace/graphTheme.js";

export type GraphScreenLocale = Locale;

function camelToSnake(key: string): string {
  return key.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
}

export type GraphScreenCopyKey = string;

function pack(locale: GraphScreenLocale) {
  return messagesForLocale(locale).graph.canvas;
}

export function graphCopy(locale: GraphScreenLocale, key: GraphScreenCopyKey): string {
  const strings = pack(locale) as unknown as Record<string, string>;
  return strings[camelToSnake(key)];
}

export function graphFormatNumber(locale: GraphScreenLocale, value: number): string {
  return formatLocaleNumber(locale, value);
}

export function graphFormatYearMonth(locale: GraphScreenLocale, value: Date): string {
  return formatLocaleYearMonth(locale, value);
}

export function graphFormatTemporalInstant(
  locale: GraphScreenLocale,
  raw: string | undefined,
  fallback: string,
): string {
  if (!raw) return fallback;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return formatLocaleDateTime(locale, date, { dateStyle: 'medium', timeStyle: 'short' });
}

export type GraphEntityShapeLabelKey = keyof (typeof en.graph.canvas)['entity_shape_labels'];

export function graphEntityShapeLabel(
  locale: GraphScreenLocale,
  shape: GraphEntityShapeLabelKey,
): string {
  const labels = pack(locale).entity_shape_labels as Record<string, string>;
  return labels[camelToSnake(shape as string)] ?? labels[shape as string];
}

export function graphNodeTypeLabel(locale: GraphScreenLocale, type: string): string {
  const labels = pack(locale).entity_shape_labels as Record<string, string>;
  return labels[type] ?? type;
}

export function graphNodeKindLabel(locale: GraphScreenLocale, type: string): string {
  const labels = pack(locale).node_kind_labels as Record<string, string>;
  return labels[type] ?? graphNodeTypeLabel(locale, type);
}

export function graphPluginCopy(locale: GraphScreenLocale) {
  return pack(locale).plugins;
}

export type GraphRegistryLogKey = string;

export function graphRegistryLog(
  locale: GraphScreenLocale,
  key: GraphRegistryLogKey,
  vars: Record<string, string>,
): string {
  const log = pack(locale).registry_log as Record<string, string>;
  return fmt(log[camelToSnake(key)], vars);
}

export function graphLoadOverlayCopy(locale: GraphScreenLocale) {
  return pack(locale).load_overlay;
}

export function graphEffectReasonsCopy(locale: GraphScreenLocale) {
  return pack(locale).effect_reasons;
}

export function graphZoomTierLabel(
  locale: GraphScreenLocale,
  tier: GraphZoomTier | string,
): string {
  const labels = (pack(locale).effect_reasons as { zoom_tier_labels: Record<string, string> })
    .zoom_tier_labels;
  return labels[tier as keyof typeof labels] ?? tier;
}

export function graphEgoModeLabel(
  locale: GraphScreenLocale,
  enabled: boolean,
  hops: number,
): string {
  if (!enabled) {
    return graphCopy(locale, "egoMode");
  }
  return fmt(pack(locale).helpers.ego_mode_active_label, { hops: formatLocaleNumber(locale, hops) });
}

export function graphEgoModeTitle(
  locale: GraphScreenLocale,
  enabled: boolean,
  hops: number,
): string {
  if (!enabled) {
    return graphCopy(locale, "egoModeTitleOff");
  }
  return fmt(pack(locale).helpers.ego_mode_active_title, { hops: formatLocaleNumber(locale, hops) });
}

export function graphStatusCounts(
  locale: GraphScreenLocale,
  nodes: number,
  edges: number,
): string {
  return fmt(pack(locale).helpers.status_counts, {
    nodes: formatLocaleNumber(locale, nodes),
    edges: formatLocaleNumber(locale, edges),
  });
}

export function graphActiveCountLabel(locale: GraphScreenLocale, count: number): string {
  return fmt(pack(locale).helpers.active_count, { count: formatLocaleNumber(locale, count) });
}

export function graphSearchResultsLabel(locale: GraphScreenLocale, count: number): string {
  const h = pack(locale).helpers;
  const template = pickCountForm(locale, count, h.search_results_one, h.search_results);
  return fmt(template, { count: formatLocaleNumber(locale, count) });
}

export function graphFocusedViewSummary(
  locale: GraphScreenLocale,
  visibleNeighbors: number,
): string {
  const total = visibleNeighbors + 1;
  return fmt(pack(locale).helpers.focused_view_summary, { total: formatLocaleNumber(locale, total) });
}

export function graphGroupedSummaryAvailable(locale: GraphScreenLocale): string {
  return pack(locale).helpers.grouped_summary_available;
}

export function graphGroupedSummaryDrillIn(locale: GraphScreenLocale): string {
  return pack(locale).helpers.grouped_summary_drill_in;
}

export function graphNeighborSummary(
  locale: GraphScreenLocale,
  visible: number,
  collapsed: number,
): string {
  return fmt(pack(locale).helpers.neighbor_summary, {
    visible: formatLocaleNumber(locale, visible),
    collapsed: formatLocaleNumber(locale, collapsed),
  });
}

export function graphDirectNeighborsSummary(
  locale: GraphScreenLocale,
  count: number,
): string {
  return fmt(pack(locale).helpers.direct_neighbors_summary, { count: formatLocaleNumber(locale, count) });
}

export function graphPluginPanelLoading(locale: GraphScreenLocale, label: string): string {
  return fmt(pack(locale).helpers.plugin_panel_loading, { label });
}

export function graphRequestFailed(locale: GraphScreenLocale, status: number): string {
  return requestFailedStatusMessage(locale, status);
}

export function graphLoadPhaseTitle(locale: GraphScreenLocale, phase: string): string {
  const titles = pack(locale).load_phase_title as Record<string, string>;
  return titles[phase] ?? titles.bootstrapping;
}

export function graphLoadStageLabel(locale: GraphScreenLocale, phase: string): string {
  const labels = pack(locale).load_stage_label as Record<string, string>;
  return labels[phase] ?? pack(locale).helpers.load_stage_fallback;
}

export function graphLoadNodesProgressMessage(
  locale: GraphScreenLocale,
  loaded: number,
  total: number | null,
): string {
  const h = pack(locale).helpers;
  const loadedStr = formatLocaleNumber(locale, loaded);
  if (total) {
    return fmt(h.load_nodes_progress, {
      loaded: loadedStr,
      total: formatLocaleNumber(locale, total),
    });
  }
  return fmt(h.load_nodes_progress_partial, { loaded: loadedStr });
}

export function graphLoadEdgesProgressMessage(
  locale: GraphScreenLocale,
  loaded: number,
  total: number | null,
): string {
  const h = pack(locale).helpers;
  const loadedStr = formatLocaleNumber(locale, loaded);
  if (total) {
    return fmt(h.load_edges_progress, {
      loaded: loadedStr,
      total: formatLocaleNumber(locale, total),
    });
  }
  return fmt(h.load_edges_progress_partial, { loaded: loadedStr });
}
