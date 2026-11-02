import { Button } from "@/components/ui/button.js";
import { cn } from "@/lib/utils.js";
import {
  graphLegendMeta,
  graphLegendPanel,
  graphLegendSwatch,
  graphLegendTitle,
  graphNeighborBtn,
  graphPanelControlBtn,
  graphPanelSummary,
  graphPanelTitle,
  graphSemanticSwatchStyle,
} from "@/lib/ui-classes/graph-ui.js";
import { fmt, formatLocaleFixedDecimals, formatLocaleNumber, pickCountForm } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";

import { graphCopy, graphFormatNumber, graphPluginCopy } from '../i18n/screen-copy.js';
import { inspectorCopy } from '../i18n/graph-inspector-copy.js';
import type { GraphPlugin } from '../lib/plugins/plugin-types.js';

const NEIGHBORHOOD_PANEL_ID = "neighborhood-panel";
const MAX_NEIGHBORS = 10;

function maxWeightBetween(graphRef: any, sourceId: string, targetId: string): number {
  let weight = 0;
  graphRef.forEachDirectedEdge(sourceId, targetId, (_edgeId: string, attrs: { weight?: number }) => {
    weight = Math.max(weight, Number(attrs.weight ?? 0));
  });
  return weight;
}

function formatNeighborMeta(
  locale: Locale,
  neighbor: { nodeType: string; degree: number; weight: number },
  p: ReturnType<typeof graphPluginCopy>["neighborhood"],
) {
  const parts = [
    neighbor.nodeType,
    fmt(p.meta_degree, { degree: formatLocaleNumber(locale, neighbor.degree) }),
  ];
  if (neighbor.weight > 0) {
    parts.push(fmt(p.meta_weight, { weight: formatLocaleFixedDecimals(locale, neighbor.weight, 2) }));
  }
  return parts.join(" · ");
}

export const neighborhoodPanelPlugin: GraphPlugin = {
  id: "neighborhood-panel",
  mount: () => {},
  unmount: () => {},
  onStateChange: () => {},
  toolbarItems: (context) => [
    {
      id: "neighborhood-toggle",
      label: graphCopy(context.locale, "pluginNeighbors"),
      title: graphCopy(context.locale, "pluginNeighborsTitle"),
      active: context.isPanelOpen(NEIGHBORHOOD_PANEL_ID),
      order: 30,
      onClick: () => context.dispatchAction({ type: "togglePanel", panelId: NEIGHBORHOOD_PANEL_ID }),
    },
  ],
  renderPanel: (context) => {
    if (!context.isPanelOpen(NEIGHBORHOOD_PANEL_ID)) {
      return null;
    }

    const p = graphPluginCopy(context.locale).neighborhood;
    const selected = context.getSelectedNodeState();
    const displayState = context.getDisplayState();
    if (!selected) {
      return {
        id: NEIGHBORHOOD_PANEL_ID,
        title: p.panel_title,
        placement: "bottom",
        order: 20,
        defaultOpen: false,
        preferredWidth: 360,
        preferredHeight: 260,
        content: (
          <div className={graphPanelSummary}>{p.empty_select}</div>
        ),
      };
    }

    const neighbors = context.graph
      .neighbors(selected.id)
      .map((neighborId) => {
        const attrs = context.graph.getNodeAttributes(neighborId);
        const weight = Math.max(
          maxWeightBetween(context.graph, selected.id, neighborId),
          maxWeightBetween(context.graph, neighborId, selected.id),
        );
        return {
          id: neighborId,
          label: String(attrs.label || neighborId),
          nodeType: String(attrs.nodeType || inspectorCopy(context.locale, "entityDefault")),
          color: String(attrs.baseColor || attrs.color || context.theme.palette.semantic[0]),
          weight,
          degree: context.graph.degree(neighborId),
        };
      })
      .sort((left, right) => {
        if (right.weight !== left.weight) {
          return right.weight - left.weight;
        }
        if (right.degree !== left.degree) {
          return right.degree - left.degree;
        }
        return left.label.localeCompare(right.label);
      })
      .slice(0, MAX_NEIGHBORS);
    const hiddenNeighborCount = displayState.selectedCollapsedNeighborIds.length;
    const aggregatedEdgeCount = context.displayGraph
      .edges()
      .map((edgeId) => context.displayGraph.getEdgeAttributes(edgeId) as { isAggregated?: boolean })
      .filter((attrs) => attrs.isAggregated).length;

    return {
      id: NEIGHBORHOOD_PANEL_ID,
      title: p.panel_title,
      placement: "bottom",
      order: 20,
      defaultOpen: false,
      preferredWidth: 360,
      preferredHeight: 260,
      content: (
        <div className={graphLegendPanel}>
          <div className={graphPanelTitle}>{selected.label}</div>
          <div className={graphPanelSummary}>
            {fmt(p.neighbor_summary, { count: graphFormatNumber(context.locale, selected.neighborCount) })}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => context.dispatchAction({ type: "collapseNeighborhood" })}
              disabled={!selected.canCollapseNeighborhood || selected.isNeighborhoodCollapsed}
              className={graphPanelControlBtn}
            >
              {p.collapse}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => context.dispatchAction({ type: "expandNeighborhood" })}
              disabled={!selected.isNeighborhoodCollapsed}
              className={graphPanelControlBtn}
            >
              {p.expand}
            </Button>
          </div>
          {hiddenNeighborCount > 0 ? (
            <div className={graphPanelSummary}>
              {fmt(p.hidden_neighbors, { count: graphFormatNumber(context.locale, hiddenNeighborCount) })}
            </div>
          ) : null}
          {aggregatedEdgeCount > 0 ? (
            <div className={graphPanelSummary}>
              {fmt(
                pickCountForm(
                  context.locale,
                  aggregatedEdgeCount,
                  p.aggregated_bundles,
                  p.aggregated_bundles_plural,
                ),
                { count: graphFormatNumber(context.locale, aggregatedEdgeCount) },
              )}
            </div>
          ) : null}
          {neighbors.length ? (
            <div className="flex flex-col gap-2">
              {neighbors.map((neighbor) => (
                <Button
                  key={neighbor.id}
                  type="button"
                  variant="ghost"
                  onClick={() => context.dispatchAction({ type: "selectNode", nodeId: neighbor.id })}
                  className={cn(graphNeighborBtn, "h-auto justify-start font-normal")}
                >
                  <span className={graphLegendSwatch} style={graphSemanticSwatchStyle(neighbor.color)} />
                  <div className="min-w-0 flex-1">
                    <div className={graphLegendTitle}>{neighbor.label}</div>
                    <div className={graphLegendMeta}>
                      {formatNeighborMeta(context.locale, neighbor, p)}
                    </div>
                  </div>
                </Button>
              ))}
            </div>
          ) : (
            <div className={graphPanelSummary}>{p.no_neighbors}</div>
          )}
        </div>
      ),
    };
  },
};
