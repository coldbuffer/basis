import { Button } from "@/components/ui/button.js";
import { cn } from "@/lib/utils.js";
import {
  graphEffectsDetails,
  graphEffectsDetailsSummary,
  graphEffectsPre,
  graphEffectsRowDesc,
  graphEffectsRowMeta,
  graphEffectsSection,
  graphEffectsSectionTitle,
  graphEffectsSignalBadge,
  graphEffectsSignalRow,
  graphEffectsSubsectionTitle,
  graphEffectsToggleBtn,
  graphEffectsToggleBtnOn,
  graphEffectsToggleRow,
  graphLegendEmpty,
  graphLegendEyebrow,
  graphLegendMeta,
  graphLegendPanel,
  graphLegendRow,
  graphLegendSwatch,
  graphLegendTitle,
  graphSemanticSwatchStyle,
} from "@/lib/ui-classes/graph-ui.js";

import { fmt, formatLocaleFixedDecimals } from "@/i18n/format.js";

import { buildGraphColorLegend } from '../lib/scene/graph-color-legend.js';
import { graphCopy, graphFormatNumber, graphPluginCopy } from '../i18n/screen-copy.js';
import type {
  GraphAnalyticsSnapshot,
  GraphDiagnosticsSnapshot,
  GraphEffectAvailability,
  GraphEffectToggle,
} from '../lib/types.js';
import type { GraphPlugin } from '../lib/plugins/plugin-types.js';
import type { GraphScreenLocale } from '../i18n/screen-copy.js';

const EFFECTS_PANEL_ID = "effects-panel";

type EffectRowConfig = {
  key: GraphEffectToggle;
  label: string;
  description: string;
};

type EffectsCopy = ReturnType<typeof graphPluginCopy>["effects"];

const LAYOUT_EFFECT_KEYS: GraphEffectToggle[] = ["autoLayoutEnabled"];

const SCENE_EFFECT_KEYS: GraphEffectToggle[] = [
  "pathPulseEnabled",
  "pathFlowEnabled",
  "lensEnabled",
  "temporalEmphasisEnabled",
  "semanticRegionsEnabled",
  "contoursEnabled",
  "edgeLabelsEnabled",
  "legendEnabled",
];

const INTELLIGENCE_EFFECT_KEYS: GraphEffectToggle[] = [
  "pathfindingEnabled",
  "communitiesEnabled",
  "centralityEnabled",
];

function effectRowKey(key: GraphEffectToggle): string {
  return key.replace(/([A-Z])/g, '_$1').toLowerCase();
}

function effectRows(locale: GraphScreenLocale, keys: GraphEffectToggle[]): EffectRowConfig[] {
  const rows = graphPluginCopy(locale).effects.rows as Record<
    string,
    { label: string; description: string }
  >;
  return keys.map((key) => {
    const row = rows[effectRowKey(key)];
    return {
      key,
      label: row.label,
      description: row.description,
    };
  });
}

const AVAILABILITY_KEYS: Record<GraphEffectToggle, keyof GraphDiagnosticsSnapshot["effectAvailability"]> = {
  pathPulseEnabled: "pathPulse",
  pathFlowEnabled: "pathFlow",
  lensEnabled: "lens",
  temporalEmphasisEnabled: "temporalEmphasis",
  semanticRegionsEnabled: "semanticRegions",
  contoursEnabled: "contours",
  pathfindingEnabled: "pathfinding",
  communitiesEnabled: "communities",
  centralityEnabled: "centrality",
  legendEnabled: "legend",
  edgeLabelsEnabled: "edgeLabels",
  autoLayoutEnabled: "autoLayout",
  diagnosticsEnabled: "diagnostics",
};

function renderAvailabilityText(availability: GraphEffectAvailability, e: EffectsCopy) {
  if (availability.available) {
    if (typeof availability.visibleSegments === "number" && typeof availability.segmentCap === "number") {
      return fmt(e.segments_progress, {
        reason: availability.reason,
        visible: availability.visibleSegments,
        cap: availability.segmentCap,
      });
    }
    return availability.reason;
  }

  return availability.detail
    ? fmt(e.availability_detail, { reason: availability.reason, detail: availability.detail })
    : availability.reason;
}

function collectFallbackLegendItems(context: Parameters<NonNullable<GraphPlugin["renderPanel"]>>[0]) {
  return buildGraphColorLegend(context.graph, context.theme)
    .sort((left, right) => right.count - left.count)
    .slice(0, context.theme.effects.legend.maxGroups);
}

function resolveAvailability(
  availabilityMap: GraphDiagnosticsSnapshot["effectAvailability"] | undefined,
  key: GraphEffectToggle,
  enabled: boolean,
  waitingReason: string,
): GraphEffectAvailability {
  return availabilityMap?.[AVAILABILITY_KEYS[key]] ?? {
    enabled,
    available: false,
    reason: waitingReason,
  };
}

function EffectToggleRow({
  label,
  description,
  checked,
  availability,
  effectsCopy,
  onToggle,
}: {
  label: string;
  description: string;
  checked: boolean;
  availability: GraphEffectAvailability;
  effectsCopy: EffectsCopy;
  onToggle: () => void;
}) {
  return (
    <div className={graphEffectsToggleRow}>
      <div className="min-w-0 flex-1">
        <div className={graphLegendTitle}>{label}</div>
        <div className={graphEffectsRowDesc}>{description}</div>
        <div className={graphEffectsRowMeta}>{renderAvailabilityText(availability, effectsCopy)}</div>
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        onClick={onToggle}
        className={cn(graphEffectsToggleBtn, checked && graphEffectsToggleBtnOn)}
      >
        {checked ? effectsCopy.toggle_on : effectsCopy.toggle_off}
      </Button>
    </div>
  );
}

function renderRegionsAndSignals(
  context: Parameters<NonNullable<GraphPlugin["renderPanel"]>>[0],
  analytics: GraphAnalyticsSnapshot | null,
  e: EffectsCopy,
) {
  const fallbackLegendItems = collectFallbackLegendItems(context);
  const semanticRegions = analytics?.semanticRegions.summaries ?? [];
  const communities = analytics?.communities.summaries ?? [];
  const centrality = analytics?.centrality.topNodes ?? [];
  const directedPath = analytics?.directedPath ?? null;

  if (!semanticRegions.length && !communities.length && !centrality.length && !fallbackLegendItems.length && !directedPath) {
    return <div className={graphLegendEmpty}>{e.regions_empty}</div>;
  }

  return (
    <div className="flex flex-col gap-2.5">
      {semanticRegions.length ? (
        <div className="flex flex-col gap-2">
          <div className={graphEffectsSubsectionTitle}>{e.semantic_regions}</div>
          {semanticRegions.map((region) => (
            <div key={region.semanticGroup} className={graphLegendRow}>
              <span className={graphLegendSwatch} style={graphSemanticSwatchStyle(region.color)} />
              <div className="min-w-0 flex-1">
                <div className={graphLegendTitle}>{region.semanticGroup}</div>
                <div className={graphLegendMeta}>
                  {fmt(e.visible_total, {
                    visible: graphFormatNumber(context.locale, region.visibleNodeCount),
                    total: graphFormatNumber(context.locale, region.nodeCount),
                  })}
                </div>
              </div>
              <div className={graphEffectsSignalBadge}>{region.anchorLabel}</div>
            </div>
          ))}
        </div>
      ) : null}

      {communities.length ? (
        <div className="flex flex-col gap-2">
          <div className={graphEffectsSubsectionTitle}>{e.community_anchors}</div>
          {communities.slice(0, 3).map((community) => (
            <div key={community.communityId} className={graphEffectsSignalRow}>
              <div className="min-w-0 flex-1">
                <div className={graphLegendTitle}>{community.anchorLabel}</div>
                <div className={graphLegendMeta}>
                  {fmt(e.community_meta, {
                    id: community.communityId,
                    visible: graphFormatNumber(context.locale, community.visibleNodeCount),
                    total: graphFormatNumber(context.locale, community.nodeCount),
                  })}
                </div>
              </div>
              <div className={graphEffectsSignalBadge}>{community.dominantSemanticGroup}</div>
            </div>
          ))}
        </div>
      ) : null}

      {centrality.length ? (
        <div className="flex flex-col gap-2">
          <div className={graphEffectsSubsectionTitle}>{e.centrality_leaders}</div>
          {centrality.slice(0, 3).map((node) => (
            <div key={node.id} className={graphEffectsSignalRow}>
              <div className="min-w-0 flex-1">
                <div className={graphLegendTitle}>{node.label}</div>
                <div className={graphLegendMeta}>
                  {fmt(e.centrality_meta, {
                    group: node.semanticGroup,
                    score: formatLocaleFixedDecimals(context.locale, node.score, 3),
                  })}
                </div>
              </div>
              <div className={graphEffectsSignalBadge}>
                {fmt(e.centrality_badge, {
                  degree: formatLocaleFixedDecimals(context.locale, node.degree, 3),
                })}
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {directedPath ? (
        <div className="flex flex-col gap-2">
          <div className={graphEffectsSubsectionTitle}>{e.directed_pathfinding}</div>
          <div className={graphEffectsSignalRow}>
            <div className="min-w-0 flex-1">
              <div className={graphLegendTitle}>{directedPath.ready ? e.path_ready : e.path_waiting}</div>
              <div className={graphLegendMeta}>{directedPath.reason}</div>
            </div>
            {directedPath.ready ? (
              <div className={graphEffectsSignalBadge}>
                {fmt(e.path_hops, {
                  count: graphFormatNumber(context.locale, directedPath.length ?? 0),
                })}
                {directedPath.verifiedAgainstActivePath ? e.path_match : ""}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}

      {!semanticRegions.length && !communities.length && !centrality.length && fallbackLegendItems.length ? (
        <div className="flex flex-col gap-2">
          <div className={graphEffectsSubsectionTitle}>{e.fallback_legend}</div>
          {fallbackLegendItems.map((item) => (
            <div key={item.id} className={graphLegendRow}>
              <span className={graphLegendSwatch} style={graphSemanticSwatchStyle(item.color)} />
              <div className="min-w-0 flex-1">
                <div className={graphLegendTitle}>{item.group}</div>
                <div className={graphLegendMeta}>
                  {fmt(graphPluginCopy(context.locale).legend.node_count, {
                    count: graphFormatNumber(context.locale, item.count),
                  })}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export const explorationEffectsPluginPhaseC: GraphPlugin = {
  id: "exploration-effects",
  mount: () => {},
  unmount: () => {},
  onStateChange: () => {},
  toolbarItems: (context) => [
    {
      id: "effects-toggle",
      label: graphCopy(context.locale, "pluginEffects"),
      title: graphCopy(context.locale, "pluginEffectsTitle"),
      active: context.isPanelOpen(EFFECTS_PANEL_ID),
      order: 18,
      onClick: () => context.dispatchAction({ type: "togglePanel", panelId: EFFECTS_PANEL_ID }),
    },
  ],
  renderPanel: (context) => {
    if (!context.isPanelOpen(EFFECTS_PANEL_ID)) {
      return null;
    }

    const e = graphPluginCopy(context.locale).effects;
    const effectsState = context.getEffectsState();
    const diagnosticsSnapshot = context.getDiagnosticsSnapshot();
    const analyticsSnapshot = context.getAnalyticsSnapshot();
    const availability = diagnosticsSnapshot?.effectAvailability;
    const showSignalsSection =
      effectsState.legendEnabled
      || effectsState.semanticRegionsEnabled
      || effectsState.communitiesEnabled
      || effectsState.centralityEnabled
      || effectsState.pathfindingEnabled;

    return {
      id: EFFECTS_PANEL_ID,
      title: e.panel_title,
      placement: "bottom",
      order: 8,
      defaultOpen: false,
      preferredWidth: 460,
      preferredHeight: 360,
      content: (
        <div className={graphLegendPanel}>
          <div className={graphLegendEyebrow}>{e.eyebrow}</div>

          <div className={graphEffectsSection}>
            <div className={graphEffectsSectionTitle}>{e.section_layout}</div>
            {effectRows(context.locale, LAYOUT_EFFECT_KEYS).map((row) => (
              <EffectToggleRow
                key={row.key}
                label={row.label}
                description={row.description}
                checked={effectsState[row.key]}
                availability={resolveAvailability(availability, row.key, effectsState[row.key], e.waiting_runtime)}
                effectsCopy={e}
                onToggle={() => context.dispatchAction({ type: "toggleEffect", effect: row.key })}
              />
            ))}
          </div>

          <div className={graphEffectsSection}>
            <div className={graphEffectsSectionTitle}>{e.section_scene}</div>
            {effectRows(context.locale, SCENE_EFFECT_KEYS).map((row) => (
              <EffectToggleRow
                key={row.key}
                label={row.label}
                description={row.description}
                checked={effectsState[row.key]}
                availability={resolveAvailability(availability, row.key, effectsState[row.key], e.waiting_runtime)}
                effectsCopy={e}
                onToggle={() => context.dispatchAction({ type: "toggleEffect", effect: row.key })}
              />
            ))}
          </div>

          <div className={graphEffectsSection}>
            <div className={graphEffectsSectionTitle}>{e.section_intelligence}</div>
            {effectRows(context.locale, INTELLIGENCE_EFFECT_KEYS).map((row) => (
              <EffectToggleRow
                key={row.key}
                label={row.label}
                description={row.description}
                checked={effectsState[row.key]}
                availability={resolveAvailability(availability, row.key, effectsState[row.key], e.waiting_runtime)}
                effectsCopy={e}
                onToggle={() => context.dispatchAction({ type: "toggleEffect", effect: row.key })}
              />
            ))}
          </div>

          {showSignalsSection ? (
            <div className={graphEffectsSection}>
              <div className={graphEffectsSectionTitle}>{e.section_regions}</div>
              {renderRegionsAndSignals(context, analyticsSnapshot, e)}
            </div>
          ) : null}

          {import.meta.env.DEV ? (
            <div className={graphEffectsSection}>
              <div className={graphEffectsSectionTitle}>{e.section_diagnostics}</div>
              <EffectToggleRow
                label={e.dev_diagnostics_label}
                description={e.dev_diagnostics_desc}
                checked={effectsState.diagnosticsEnabled}
                availability={resolveAvailability(
                  availability,
                  "diagnosticsEnabled",
                  effectsState.diagnosticsEnabled,
                  e.waiting_runtime,
                )}
                effectsCopy={e}
                onToggle={() => context.dispatchAction({ type: "toggleEffect", effect: "diagnosticsEnabled" })}
              />
              {effectsState.diagnosticsEnabled && diagnosticsSnapshot ? (
                <details className={graphEffectsDetails}>
                  <summary className={graphEffectsDetailsSummary}>{e.runtime_snapshot}</summary>
                  <pre className={graphEffectsPre}>
                    {JSON.stringify({ diagnostics: diagnosticsSnapshot, analytics: analyticsSnapshot }, null, 2)}
                  </pre>
                </details>
              ) : null}
            </div>
          ) : null}
        </div>
      ),
    };
  },
};
