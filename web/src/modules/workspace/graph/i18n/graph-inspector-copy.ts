import { fmt, formatLocaleNumber, pickCountForm } from '@/i18n/format.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import type { GraphScreenLocale } from './screen-copy.js';

function camelToSnake(key: string): string {
  return key.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
}

function pack(locale: GraphScreenLocale) {
  return messagesForLocale(locale).graph.canvas;
}

export type InspectorCopyKey = string;

export function inspectorCopy(locale: GraphScreenLocale, key: InspectorCopyKey): string {
  const inspector = pack(locale).inspector as unknown as Record<string, string>;
  return inspector[camelToSnake(key)];
}

const PATH_BAND_LABEL_KEYS: Record<string, 'inspector_path_band_direct' | 'inspector_path_band_near' | 'inspector_path_band_mid' | 'inspector_path_band_distant'> = {
  direct: 'inspector_path_band_direct',
  near: 'inspector_path_band_near',
  mid: 'inspector_path_band_mid',
  'mid-range': 'inspector_path_band_mid',
  distant: 'inspector_path_band_distant',
};

export function inspectorPathBandBadge(
  locale: GraphScreenLocale,
  band: string,
  hopCount: number,
): string {
  const h = pack(locale).helpers;
  const bandKey = PATH_BAND_LABEL_KEYS[band] ?? 'inspector_path_band_distant';
  const bandLabel = h[bandKey];
  const hopsTemplate = pickCountForm(
    locale,
    hopCount,
    h.inspector_path_band_hops_one,
    h.inspector_path_band_hops,
  );
  const hops = fmt(hopsTemplate, { hops: formatLocaleNumber(locale, hopCount) });
  return `${bandLabel} · ${hops}`;
}

export function inspectorAltPathsBadge(locale: GraphScreenLocale, count: number): string {
  const h = pack(locale).helpers;
  const template = pickCountForm(locale, count, h.inspector_alt_paths_one, h.inspector_alt_paths);
  return fmt(template, { count: formatLocaleNumber(locale, count) });
}

export function inspectorBadgeCount(
  locale: GraphScreenLocale,
  count: number,
  kind: 'sourceFields' | 'candidateLinks',
): string {
  const h = pack(locale).helpers;
  const template =
    kind === 'sourceFields' ? h.inspector_source_fields_badge : h.inspector_candidate_links_badge;
  return fmt(template, { count: formatLocaleNumber(locale, count) });
}

export function inspectorFocusTitle(
  locale: GraphScreenLocale,
  nodeId: string,
  isBottleneck: boolean,
): string {
  const h = pack(locale).helpers;
  const template = isBottleneck ? h.inspector_focus_bottleneck : h.inspector_focus;
  return fmt(template, { nodeId });
}

export function inspectorHopsSummary(locale: GraphScreenLocale, hopCount: number): string {
  const h = pack(locale).helpers;
  return fmt(h.inspector_hops, { hops: formatLocaleNumber(locale, hopCount) });
}

export function inspectorCanonicalNodeLine(locale: GraphScreenLocale, nodeId: string): string {
  return fmt(pack(locale).helpers.inspector_canonical_node, { nodeId });
}
