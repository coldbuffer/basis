import {
  graphDetailLabel,
  graphDetailRow,
  graphDetailValue,
  graphLegendEyebrow,
  graphLegendPanel,
  graphTemporalChip,
  graphTemporalChipAccent,
} from "@/lib/ui-classes/graph-ui.js";
import { fmt } from "@/i18n/format.js";

import {
  graphCopy,
  graphFormatNumber,
  graphFormatTemporalInstant,
  graphFormatYearMonth,
  graphPluginCopy,
} from '../i18n/screen-copy.js';
import type { GraphPlugin } from '../lib/plugins/plugin-types.js';

const TEMPORAL_PANEL_ID = "temporal-panel";

export const temporalOverlayPlugin: GraphPlugin = {
  id: "temporal-overlay",
  mount: () => {},
  unmount: () => {},
  onStateChange: () => {},
  toolbarItems: (context) => [
    {
      id: "temporal-toggle",
      label: graphCopy(context.locale, "pluginTemporal"),
      title: graphCopy(context.locale, "pluginTemporalTitle"),
      active: context.isPanelOpen(TEMPORAL_PANEL_ID),
      order: 40,
      onClick: () => context.dispatchAction({ type: "togglePanel", panelId: TEMPORAL_PANEL_ID }),
    },
  ],
  renderOverlay: (context) => {
    const temporal = context.getTemporalState();
    if (!temporal?.currentTime) {
      return null;
    }

    const p = graphPluginCopy(context.locale).temporal;
    const label = temporal.currentTime
      ? graphFormatYearMonth(context.locale, temporal.currentTime)
      : p.no_time_selected;
    return {
      id: "temporal-overlay-chip",
      layer: 1,
      order: 10,
      element: (
        <div className={graphTemporalChip}>
          <span className={graphTemporalChipAccent}>{graphCopy(context.locale, "pluginTemporal")}</span>
          <span>{label}</span>
          {typeof temporal.activeNodeCount === "number" ? (
            <span className="text-muted-foreground">
              {fmt(p.active_chip, { count: graphFormatNumber(context.locale, temporal.activeNodeCount) })}
            </span>
          ) : null}
        </div>
      ),
    };
  },
  renderPanel: (context) => {
    if (!context.isPanelOpen(TEMPORAL_PANEL_ID)) {
      return null;
    }

    const temporal = context.getTemporalState();
    const p = graphPluginCopy(context.locale).temporal;
    return {
      id: TEMPORAL_PANEL_ID,
      title: p.panel_title,
      placement: "bottom",
      order: 30,
      defaultOpen: false,
      preferredWidth: 320,
      preferredHeight: 220,
      content: (
        <div className={graphLegendPanel}>
          <div className={graphLegendEyebrow}>{p.scrubber_eyebrow}</div>
          <div className={graphDetailRow}>
            <span className={graphDetailLabel}>{p.current}</span>
            <span className={graphDetailValue}>
              {temporal?.currentTime
                ? graphFormatYearMonth(context.locale, temporal.currentTime)
                : p.no_time_selected}
            </span>
          </div>
          <div className={graphDetailRow}>
            <span className={graphDetailLabel}>{p.bounds}</span>
            <span className={graphDetailValue}>
              {graphFormatTemporalInstant(context.locale, temporal?.minDate, p.bounds_epoch)}
              {' → '}
              {graphFormatTemporalInstant(context.locale, temporal?.maxDate, p.bounds_now)}
            </span>
          </div>
          <div className={graphDetailRow}>
            <span className={graphDetailLabel}>{p.active_nodes}</span>
            <span className={graphDetailValue}>
              {typeof temporal?.activeNodeCount === "number"
                ? graphFormatNumber(context.locale, temporal.activeNodeCount)
                : p.all_nodes}
            </span>
          </div>
        </div>
      ),
    };
  },
};
