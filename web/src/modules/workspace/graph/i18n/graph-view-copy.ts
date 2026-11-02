import { fmt } from '@/i18n/format.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import type { GraphScreenLocale } from './screen-copy.js';
import type { FocusedUnavailableReason, GroupedViewUnavailableReason } from '../lib/types.js';

function pack(locale: GraphScreenLocale) {
  return messagesForLocale(locale).graph.canvas;
}

export function groupedViewReasonText(
  reason: GroupedViewUnavailableReason | null | undefined,
  locale: GraphScreenLocale = 'en',
): string | null {
  if (!reason) {
    return null;
  }

  const g = pack(locale);
  switch (reason.code) {
    case 'communities-undetected':
      return g.grouped_view.communities_undetected;
    case 'community-nodes-missing':
      return g.grouped_view.community_nodes_missing;
    case 'invalid-community-layout':
      return fmt(g.helpers.invalid_community_layout, { nodeId: reason.nodeId });
    case 'missing-grouped-node':
      return fmt(g.helpers.missing_grouped_node, { edgeId: reason.edgeId });
  }
}

export function focusedUnavailableReasonText(
  reason: FocusedUnavailableReason | null | undefined,
  locale: GraphScreenLocale = 'en',
): string | null {
  if (!reason) {
    return null;
  }

  const f = pack(locale).focused_mode;
  switch (reason.code) {
    case 'no-selection':
      return f.no_selection;
    case 'grouped-unresolvable':
      return f.grouped_unresolvable;
    case 'not-in-graph':
      return f.not_in_graph;
  }
}
