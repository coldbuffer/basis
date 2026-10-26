import type { LocaleMessages } from '@/i18n/en.js';
import type { SidebarMenuKey } from '@/lib/nav/nav-config.js';

/** Resolve sidebar `labelKey` to module-scattered menu copy. */
export function workspaceNavMenuLabel(t: LocaleMessages, labelKey: SidebarMenuKey): string {
  switch (labelKey) {
    case 'graph':
      return t.graph.menu.graph;
    case 'search':
      return t.search.menu.search;
    case 'sources':
      return t.library.menu.sources;
    case 'processing':
      return t.processing.menu.processing;
    case 'entities':
      return t.entities.menu.entities;
    case 'connectionsSync':
      return t.connectors.menu.connections_sync;
    case 'ontology':
      return t.ontology.menu.ontology;
    case 'analyze':
      return t.analyze.menu.analyze;
    case 'vocabulary':
      return t.vocabulary.menu.vocabulary;
    case 'review':
      return t.review.menu.review;
    case 'dataQuality':
      return t.data_quality.menu.data_quality;
    case 'activityLog':
      return t.activity_log.menu.activity_log;
    case 'lineage':
      return t.lineage.menu.lineage;
    case 'graphDiff':
      return t.graph.menu.graph_diff;
    case 'integration':
      return t.integration.menu.integration;
    case 'settings':
      return t.settings.menu.settings;
    case 'alerts':
      return t.alerts.menu.alerts;
    default: {
      const _exhaustive: never = labelKey;
      return _exhaustive;
    }
  }
}
