import { useEffect, useMemo, useRef, useCallback, forwardRef, useImperativeHandle, useState, type ReactNode } from "react";
import Sigma from "sigma";
import FA2Layout from "graphology-layout-forceatlas2/worker";
import { graph, type EdgeAttributes, type NodeAttributes } from '@/lib/workspace/graphStore';
import type { GraphBehavior, GraphBehaviorContext, GraphBehaviorActionRequest } from '../lib/behaviors/behavior-types.js';
import { hoverActivationBehavior } from '../lib/behaviors/behavior-hover-activation-behavior.js';
import { clickSelectionBehavior } from '../lib/behaviors/behavior-click-selection-behavior.js';
import { focusCameraBehavior } from '../lib/behaviors/behavior-focus-camera-behavior.js';
import { createSearchFocusBehavior } from '../lib/behaviors/behavior-search-focus-behavior.js';
import { createPathHighlightBehavior } from '../lib/behaviors/behavior-path-highlight-behavior.js';
import { fitViewBehavior } from '../lib/behaviors/behavior-fit-view-behavior.js';
import { createViewModeSwitchBehavior } from '../lib/behaviors/behavior-view-mode-switch-behavior.js';
import {
  GRAPH_THEME,
  getZoomTier,
  type GraphBadgeKind,
  type GraphZoomTier,
  withAlpha,
  zoomTierAtLeast,
} from "@/lib/workspace/graphTheme.js";
import {
  buildFocusSetInGraph,
  buildEdgeEndpointSet,
  buildPathEdgeSet,
  collectInteractionRefreshTargets,
  createInteractionState,
  isEdgeInteractable,
  classifyFullGraphEdge,
  mapFullEdgeClassToVisualState,
  resolveEdgeElementStyle,
  resolveEdgeVisualState,
  resolveDistanceEdgeStyle,
  resolveDistanceNodeStyle,
  resolveNodeElementStyle,
  resolveNodeVisualState,
} from '../lib/scene/graph-scene-state.js';
import { fmt, formatLocaleFixedDecimals, formatLocaleNumber } from "@/i18n/format.js";
import { isEdgeTypeSuppressed, edgeTypeOf } from '../lib/graph-edge-types.js';
import { isNodeKeywordSuppressed, normalizeKeywordFilter } from '../lib/graph-keyword-filter.js';
import { isNodeTypeSuppressed } from '../lib/graph-node-types.js';

import { buildGraphAnalyticsSnapshot, computeGraphAnalyticsBase } from '../lib/graph-analytics.js';
import {
  graphEffectReasonsCopy,
  graphZoomTierLabel,
  type GraphScreenLocale,
} from '../i18n/screen-copy.js';
import {
  collectVisibleNodeSamples,
  drawContourLayer,
  drawLensLayer,
  drawPathEffectsLayer,
  drawSemanticRegionsLayer,
  drawTemporalEmphasisLayer,
  getNodeViewportPoint,
  getViewportNodeSize,
  syncGraphOverlayCanvas,
  type PathSegmentOverlay,
  type ViewportPoint,
} from '../lib/scene/graph-scene-layers.js';
import {
  SEMANTICA_EDGE_PROGRAM_CLASSES,
  SEMANTICA_NODE_PROGRAM_CLASSES,
  drawSemanticaNodeHover,
  drawSemanticaNodeLabel,
} from '../lib/scene/sigma-native-rendering.js';
import { getSigmaCanvasLabelSettings } from "@/modules/workspace/graph/lib/graph/basis-graph-theme-sync";
import {
  graphCanvasHost,
  graphCanvasOverlay,
  graphCanvasRoot,
  graphFitViewBtn,
  graphPluginOverlayLayer,
  graphPluginOverlaySlot,
} from "@/lib/ui-classes/graph-ui.js";
import { Button } from "@/components/ui/button.js";
import { cn } from "@/lib/utils.js";
import {
  buildGraphStructureCurveCache,
  clearGraphStructureLayer,
  createGraphStructureCacheKey,
  drawGraphStructureLayer,
  evaluateGraphStructureLayerGate,
  getGraphStructureLayerDiagnostics,
  type GraphStructureCurveCache,
} from '../lib/scene/graph-structure-layer.js';
import type {
  GraphAnalyticsSnapshot,
  GraphCameraState,
  GraphDistanceVisualState,
  GraphDisplayMeta,
  GraphDisplayStateSnapshot,
  GraphDiagnosticsSnapshot,
  GraphEffectsState,
  GraphFullEdgeClass,
  GraphFullEdgeClassCounts,
  GraphFullEdgeClassDiagnostics,
  GraphInteractionState,
  GraphLayoutStatus,
  GraphRuntimeDiagnosticsSnapshot,
  GraphStructureLayerDiagnostics,
  GraphTemporalState,
  GraphViewMode,
} from '../lib/types.js';
import {
  graphDiffEdgeKey,
  graphDiffEdgeTouchesChange,
  type GraphDiffOverlayState,
} from "@/modules/workspace/graph/lib/diff/graph-diff-overlay.js";
import type { GraphSceneGraph, GraphSceneRuntime } from '../lib/scene/scene.js';

export type { GraphViewMode } from '../lib/types.js';

export interface GraphCanvasHandle {
  fitView: () => void;
  focusNode: (nodeId: string) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  requestRender: () => void;
  getCameraState: () => GraphCameraState | null;
}

export interface GraphCanvasProps {
  graphVersion: number;
  graphReady: boolean;
  displayGraph: GraphSceneGraph;
  displayMeta: GraphDisplayMeta;
  displayState?: GraphDisplayStateSnapshot;
  onNodeClick: (nodeId: string) => void;
  onEdgeClick?: (edgeId: string) => void;
  selectedNodeId: string;
  focusedNodeId: string;
  selectedEdgeId: string;
  activePath?: string[];
  activePathEdgeIds?: string[];
  distanceVisualState?: GraphDistanceVisualState;
  effectsState: GraphEffectsState;
  temporalState?: GraphTemporalState | null;
  isLayoutRunning: boolean;
  onLayoutRunningChange?: (running: boolean) => void;
  layoutSource?: string;
  onLayoutStatusChange?: (status: GraphLayoutStatus) => void;
  viewMode: GraphViewMode;
  className?: string;
  showFitViewButton?: boolean;
  pluginOverlays?: ReactNode[];
  onSceneRuntimeChange?: (runtime: GraphSceneRuntime | null) => void;
  onInteractionStateChange?: (interactionState: GraphInteractionState) => void;
  onCameraStateChange?: (cameraState: GraphCameraState) => void;
  onDiagnosticsChange?: (diagnostics: GraphRuntimeDiagnosticsSnapshot) => void;
  onAnalyticsChange?: (analytics: GraphAnalyticsSnapshot | null) => void;
  locale?: GraphScreenLocale;
  /** Node types switched off in the type filter. Those nodes stay in the graph but are not drawn. */
  hiddenNodeTypes?: readonly string[];
  /** Edge types switched off in the type filter. Those edges stay in the graph but are not drawn. */
  hiddenEdgeTypes?: readonly string[];
  /** Non-empty value hides nodes that do not match label, content, type, or id. */
  keywordFilter?: string;
  /** F-DIFF-01 canvas preview: emphasize added/modified nodes; dim the rest. */
  diffOverlay?: GraphDiffOverlayState | null;
}

type EffectReasons = ReturnType<typeof graphEffectReasonsCopy>;

const FA2_SETTINGS = {
  iterations: 50,
  settings: {
    barnesHutOptimize: true,
    barnesHutTheta: 0.5,
    adjustSizes: false,
    gravity: 0.16,
    scalingRatio: 7.5,
    edgeWeightInfluence: 0.3,
    linLogMode: true,
    strongGravityMode: false,
    slowDown: 18,
  },
};

const FULL_GRAPH_LAYOUT_SETTLE_MS = 4_500;

const GROUPED_FA2_SETTINGS = {
  iterations: GRAPH_THEME.grouped.layout.iterations,
  settings: {
    barnesHutOptimize: true,
    barnesHutTheta: 0.5,
    adjustSizes: true,
    gravity: GRAPH_THEME.grouped.layout.gravity,
    scalingRatio: GRAPH_THEME.grouped.layout.scalingRatio,
    edgeWeightInfluence: GRAPH_THEME.grouped.layout.edgeWeightInfluence,
    linLogMode: false,
    strongGravityMode: false,
    slowDown: GRAPH_THEME.grouped.layout.slowDown,
  },
};

const SIGMA_SETTINGS_BASE = {
  allowInvalidContainer: true,
  labelRenderedSizeThreshold: 6,
  minEdgeThickness: 1.35,
  defaultNodeType: "circle",
  defaultEdgeType: "line",
  hideLabelsOnMove: true,
  hideEdgesOnMove: true,
  enableEdgeEvents: true,
  // #1009: edge labels (the edge `type` — "works_for", "leads", ...) were
  // hardcoded off, so edge text never rendered regardless of data. The
  // labelDensity / labelGridCellSize / labelRenderedSizeThreshold settings
  // below already throttle label density for both nodes and edges.
  renderEdgeLabels: true,
  labelDensity: 0.7,
  labelGridCellSize: 140,
  zIndex: true,
  minCameraRatio: 0.04,
  maxCameraRatio: 8,
  webGLTarget: "webgl2" as const,
  nodeProgramClasses: SEMANTICA_NODE_PROGRAM_CLASSES,
  edgeProgramClasses: SEMANTICA_EDGE_PROGRAM_CLASSES,
  defaultDrawNodeLabel: drawSemanticaNodeLabel,
  defaultDrawNodeHover: drawSemanticaNodeHover,
};

function buildSigmaSettings(renderEdgeLabels: boolean) {
  return {
    ...SIGMA_SETTINGS_BASE,
    ...getSigmaCanvasLabelSettings(),
    renderEdgeLabels,
  };
}

function applySigmaCanvasThemeSettings(sigma: Sigma) {
  const labelSettings = getSigmaCanvasLabelSettings();
  sigma.setSetting("labelColor", labelSettings.labelColor);
  sigma.setSetting("edgeLabelColor", labelSettings.edgeLabelColor);
}

const DEBUG_GRAPH_RUNTIME = import.meta.env.DEV;

function debugGraphRuntime(message: string, payload?: Record<string, unknown>) {
  if (!DEBUG_GRAPH_RUNTIME) {
    return;
  }
  console.debug(`[GraphCanvas] ${message}`, payload ?? {});
}

function syncDisplayNodePositionsFromStore(
  targetGraph: GraphSceneGraph,
  storeGraph: typeof graph,
): number {
  let changed = 0;

  targetGraph.forEachNode((nodeId, attrs) => {
    if (!storeGraph.hasNode(nodeId)) {
      return;
    }

    const sourceAttrs = storeGraph.getNodeAttributes(nodeId) as NodeAttributes;
    const nextX = Number(sourceAttrs.x);
    const nextY = Number(sourceAttrs.y);
    const currentAttrs = attrs as NodeAttributes;
    if (!Number.isFinite(nextX) || !Number.isFinite(nextY)) {
      return;
    }

    const currentX = Number(currentAttrs.x);
    const currentY = Number(currentAttrs.y);
    if (Math.abs(currentX - nextX) <= 0.001 && Math.abs(currentY - nextY) <= 0.001) {
      return;
    }

    targetGraph.mergeNodeAttributes(nodeId, {
      x: nextX,
      y: nextY,
    });
    changed += 1;
  });

  return changed;
}

function resolveGroupedSelectionNodeId(
  displayGraph: GraphSceneGraph,
  nodeId: string,
): string | null {
  if (!nodeId) {
    return null;
  }
  if (displayGraph.hasNode(nodeId)) {
    return nodeId;
  }

  let resolvedNodeId: string | null = null;
  displayGraph.forEachNode((candidateId, attrs) => {
    if (resolvedNodeId) {
      return;
    }
    const communityGroup = (attrs as NodeAttributes).properties?.__communityGroup as
      | {
          anchorNodeId?: string | null;
          memberNodeIds?: string[];
          sampleNodeIds?: string[];
        }
      | undefined;
    if (!communityGroup) {
      return;
    }

    if (communityGroup.anchorNodeId === nodeId) {
      resolvedNodeId = candidateId;
      return;
    }

    if (communityGroup.sampleNodeIds?.includes(nodeId) || communityGroup.memberNodeIds?.includes(nodeId)) {
      resolvedNodeId = candidateId;
    }
  });

  return resolvedNodeId;
}

function collectSelectionContextNodeIds(
  displayGraph: GraphSceneGraph,
  displayState: GraphDisplayStateSnapshot | undefined,
  nodeId: string,
): string[] {
  if (!nodeId) {
    return [];
  }

  const resolvedNodeId = resolveGroupedSelectionNodeId(displayGraph, nodeId);
  if (!resolvedNodeId) {
    return [];
  }

  const neighborIds = (displayState?.selectedVisibleNeighborIds ?? [])
    .filter((neighborId) => displayGraph.hasNode(neighborId))
    .slice(0, GRAPH_THEME.focus.maxNeighbors);

  return Array.from(new Set([resolvedNodeId, ...neighborIds]));
}

function computeGraphSpaceBounds(
  displayGraph: GraphSceneGraph,
  nodeIds: string[],
): { minX: number; maxX: number; minY: number; maxY: number; count: number } | null {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let count = 0;

  nodeIds.forEach((nodeId) => {
    if (!displayGraph.hasNode(nodeId)) {
      return;
    }

    const attrs = displayGraph.getNodeAttributes(nodeId) as NodeAttributes;
    const x = Number(attrs.x);
    const y = Number(attrs.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return;
    }

    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
    count += 1;
  });

  if (count === 0) {
    return null;
  }

  return { minX, maxX, minY, maxY, count };
}

type GraphSpaceBounds = NonNullable<ReturnType<typeof computeGraphSpaceBounds>>;
type SigmaCustomBBox = {
  x: [number, number];
  y: [number, number];
};

type DisplayFitSignature = {
  graphVersion: number;
  viewMode: GraphViewMode;
  layoutMode: GraphDisplayMeta["layoutMode"];
  displayGraph: GraphSceneGraph;
};

function isSameDisplayFitSignature(
  left: DisplayFitSignature | null,
  right: DisplayFitSignature,
): boolean {
  if (!left) {
    return false;
  }

  return left.graphVersion === right.graphVersion
    && left.viewMode === right.viewMode
    && left.layoutMode === right.layoutMode
    && left.displayGraph === right.displayGraph;
}

function computeDisplayedNodeBounds(
  sigma: Sigma,
  nodeIds: string[],
): GraphSpaceBounds | null {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  let count = 0;

  nodeIds.forEach((nodeId) => {
    const displayData = sigma.getNodeDisplayData(nodeId);
    if (!displayData) {
      return;
    }

    const x = Number(displayData.x);
    const y = Number(displayData.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return;
    }

    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
    count += 1;
  });

  if (count === 0) {
    return null;
  }

  return { minX, maxX, minY, maxY, count };
}

function computeDisplayedGraphBounds(
  sigma: Sigma,
  displayGraph: GraphSceneGraph,
): GraphSpaceBounds | null {
  const nodeIds: string[] = [];
  displayGraph.forEachNode((nodeId) => {
    nodeIds.push(nodeId);
  });
  return computeDisplayedNodeBounds(sigma, nodeIds);
}

function computeCameraTargetFromBounds(
  sigma: Sigma,
  bounds: SigmaCustomBBox,
): { x: number; y: number; ratio: number; angle: number } | null {
  const camera = sigma.getCamera();
  const cameraState = camera.getState();
  const viewRect = sigma.viewRectangle();

  const currentWidth = Math.abs(viewRect.x2 - viewRect.x1);
  const currentHeight = Math.abs(viewRect.height);
  const targetWidth = Math.abs(bounds.x[1] - bounds.x[0]);
  const targetHeight = Math.abs(bounds.y[1] - bounds.y[0]);
  const centerX = (bounds.x[0] + bounds.x[1]) / 2;
  const centerY = (bounds.y[0] + bounds.y[1]) / 2;

  if (
    ![currentWidth, currentHeight, targetWidth, targetHeight, centerX, centerY].every(Number.isFinite)
    || currentWidth <= 0
    || currentHeight <= 0
    || targetWidth <= 0
    || targetHeight <= 0
  ) {
    return null;
  }

  const fitScale = Math.max(targetWidth / currentWidth, targetHeight / currentHeight);
  const nextRatio = camera.getBoundedRatio(cameraState.ratio * fitScale);
  if (!Number.isFinite(nextRatio) || nextRatio <= 0) {
    return null;
  }

  return {
    x: centerX,
    y: centerY,
    ratio: nextRatio,
    angle: cameraState.angle,
  };
}

function expandGraphSpaceBounds(
  bounds: GraphSpaceBounds,
  referenceBounds: GraphSpaceBounds | null,
  options?: {
    paddingRatio?: number;
    minSpanRatio?: number;
    minSpanFloor?: number;
  },
): SigmaCustomBBox | null {
  const paddingRatio = options?.paddingRatio ?? 0.12;
  const minSpanRatio = options?.minSpanRatio ?? 0.03;
  const minSpanFloor = options?.minSpanFloor ?? 1;

  const referenceSpanX = Math.max(
    referenceBounds ? referenceBounds.maxX - referenceBounds.minX : 0,
    minSpanFloor,
  );
  const referenceSpanY = Math.max(
    referenceBounds ? referenceBounds.maxY - referenceBounds.minY : 0,
    minSpanFloor,
  );

  const spanX = Math.max(bounds.maxX - bounds.minX, 0);
  const spanY = Math.max(bounds.maxY - bounds.minY, 0);
  const minSpanX = Math.max(referenceSpanX * minSpanRatio, minSpanFloor);
  const minSpanY = Math.max(referenceSpanY * minSpanRatio, minSpanFloor);
  const targetSpanX = Math.max(spanX, minSpanX);
  const targetSpanY = Math.max(spanY, minSpanY);
  const centerX = (bounds.minX + bounds.maxX) / 2;
  const centerY = (bounds.minY + bounds.maxY) / 2;
  if (![targetSpanX, targetSpanY, centerX, centerY].every(Number.isFinite)) {
    return null;
  }

  const paddedSpanX = targetSpanX * (1 + paddingRatio * 2);
  const paddedSpanY = targetSpanY * (1 + paddingRatio * 2);
  if (paddedSpanX <= 0 || paddedSpanY <= 0) {
    return null;
  }

  return {
    x: [centerX - paddedSpanX / 2, centerX + paddedSpanX / 2],
    y: [centerY - paddedSpanY / 2, centerY + paddedSpanY / 2],
  };
}

function isPointNearViewport(point: ViewportPoint, width: number, height: number, padding = 96) {
  return point.x >= -padding
    && point.y >= -padding
    && point.x <= width + padding
    && point.y <= height + padding;
}

function collectPathSegments(
  sigma: Sigma,
  path: string[],
  pathEdgeIds: string[],
  zoomTier: GraphZoomTier,
  viewportWidth: number,
  viewportHeight: number,
): PathSegmentOverlay[] {
  const segments: PathSegmentOverlay[] = [];

  for (let index = 0; index < path.length - 1; index += 1) {
    const sourceId = path[index];
    const targetId = path[index + 1];
    const sourceData = sigma.getNodeDisplayData(sourceId);
    const targetData = sigma.getNodeDisplayData(targetId);
    if (!sourceData || !targetData) {
      continue;
    }

    const source = sigma.framedGraphToViewport({ x: sourceData.x, y: sourceData.y });
    const target = sigma.framedGraphToViewport({ x: targetData.x, y: targetData.y });
    if (!isPointNearViewport(source, viewportWidth, viewportHeight) && !isPointNearViewport(target, viewportWidth, viewportHeight)) {
      continue;
    }

    const attrs = pathEdgeIds[index] && graph.hasEdge(pathEdgeIds[index])
      ? (graph.getEdgeAttributes(pathEdgeIds[index]) as EdgeAttributes)
      : ({
          baseColor: GRAPH_THEME.palette.accent.path,
          baseSize: 1.2,
          edgeVariant: "pathSignal",
          arrowVisibilityPolicy: "always",
        } as EdgeAttributes);
    const pathStyle = resolveEdgeElementStyle(GRAPH_THEME, zoomTier, "path", attrs, sourceId, targetId);
    if (!pathStyle.color || !pathStyle.size) {
      continue;
    }

    segments.push({
      sourceId,
      targetId,
      source,
      target,
      color: pathStyle.color,
      size: pathStyle.size,
    });
  }

  return segments;
}

function buildEffectAvailability(
  reasons: EffectReasons,
  locale: GraphScreenLocale,
  interactionState: GraphInteractionState,
  effectsState: GraphEffectsState,
  temporalState: GraphTemporalState | null | undefined,
  analytics: GraphAnalyticsSnapshot | null,
  isLayoutRunning: boolean,
  sigma: Sigma | null,
  viewportWidth: number,
  viewportHeight: number,
): GraphDiagnosticsSnapshot["effectAvailability"] {
  const visiblePathSegments = sigma
    ? collectPathSegments(
        sigma,
        interactionState.activePath,
        interactionState.activePathEdgeIds,
        interactionState.zoomTier,
        viewportWidth,
        viewportHeight,
      ).length
    : 0;
  const hasActivePath = interactionState.activePath.length > 1;
  const pulseTierReady = zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.pathPulse.minZoomTier);
  const flowTierReady = zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.pathFlow.minZoomTier);
  const lensTierReady = zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.lens.minZoomTier);
  const temporalTierReady = zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.temporalEmphasis.minZoomTier);
  const regionsTierReady = zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.semanticRegions.minZoomTier);
  const contoursTierReady = zoomTierAtLeast(interactionState.zoomTier, GRAPH_THEME.effects.contours.minZoomTier);
  const hasPrimaryNode = Boolean(interactionState.hoveredNodeId || interactionState.selectedNodeId);
  const layoutReason = reasons.layout_settling;

  const pathPulse = !effectsState.pathPulseEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : isLayoutRunning
      ? { enabled: true, available: false, reason: layoutReason }
    : !hasActivePath
      ? { enabled: true, available: false, reason: reasons.no_active_path }
      : !pulseTierReady
        ? {
            enabled: true,
            available: false,
            reason: reasons.disabled_by_zoom_tier,
            detail: fmt(reasons.requires_zoom_tier, {
              tier: graphZoomTierLabel(locale, GRAPH_THEME.effects.pathPulse.minZoomTier),
            }),
          }
        : visiblePathSegments === 0
          ? { enabled: true, available: false, reason: reasons.path_off_screen }
          : visiblePathSegments > GRAPH_THEME.effects.pathPulse.maxSegments
            ? {
                enabled: true,
                available: false,
                reason: reasons.disabled_by_path_size_cap,
                detail: fmt(reasons.visible_segments, {
                  count: formatLocaleNumber(locale, visiblePathSegments),
                }),
                visibleSegments: visiblePathSegments,
                segmentCap: GRAPH_THEME.effects.pathPulse.maxSegments,
              }
            : {
                enabled: true,
                available: true,
                reason: reasons.ready,
                visibleSegments: visiblePathSegments,
                segmentCap: GRAPH_THEME.effects.pathPulse.maxSegments,
              };

  const pathFlow = !effectsState.pathFlowEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : isLayoutRunning
      ? { enabled: true, available: false, reason: layoutReason }
    : !hasActivePath
      ? { enabled: true, available: false, reason: reasons.no_active_path }
      : !flowTierReady
        ? {
            enabled: true,
            available: false,
            reason: reasons.disabled_by_zoom_tier,
            detail: fmt(reasons.requires_zoom_tier, {
              tier: graphZoomTierLabel(locale, GRAPH_THEME.effects.pathFlow.minZoomTier),
            }),
          }
        : visiblePathSegments === 0
          ? { enabled: true, available: false, reason: reasons.path_off_screen }
          : visiblePathSegments > GRAPH_THEME.effects.pathFlow.maxSegments
            ? {
                enabled: true,
                available: false,
                reason: reasons.disabled_by_path_size_cap,
                detail: fmt(reasons.visible_segments, {
                  count: formatLocaleNumber(locale, visiblePathSegments),
                }),
                visibleSegments: visiblePathSegments,
                segmentCap: GRAPH_THEME.effects.pathFlow.maxSegments,
              }
            : {
                enabled: true,
                available: true,
                reason: reasons.ready,
                visibleSegments: visiblePathSegments,
                segmentCap: GRAPH_THEME.effects.pathFlow.maxSegments,
              };

  const lens = !effectsState.lensEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : isLayoutRunning
      ? { enabled: true, available: false, reason: layoutReason }
    : !hasPrimaryNode
      ? { enabled: true, available: false, reason: reasons.no_focal_node }
      : !lensTierReady
        ? {
            enabled: true,
            available: false,
            reason: reasons.disabled_by_zoom_tier,
            detail: fmt(reasons.requires_zoom_tier, {
              tier: graphZoomTierLabel(locale, GRAPH_THEME.effects.lens.minZoomTier),
            }),
          }
        : { enabled: true, available: true, reason: reasons.ready };

  const temporalEmphasis = !effectsState.temporalEmphasisEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : isLayoutRunning
      ? { enabled: true, available: false, reason: layoutReason }
    : !temporalState?.currentTime
      ? { enabled: true, available: false, reason: reasons.no_temporal_focus_time }
      : !temporalTierReady
        ? {
            enabled: true,
            available: false,
            reason: reasons.disabled_by_zoom_tier,
            detail: fmt(reasons.requires_zoom_tier, {
              tier: graphZoomTierLabel(locale, GRAPH_THEME.effects.temporalEmphasis.minZoomTier),
            }),
          }
        : { enabled: true, available: true, reason: reasons.ready };

  const semanticRegions = !effectsState.semanticRegionsEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : isLayoutRunning
      ? { enabled: true, available: false, reason: layoutReason }
    : !regionsTierReady
      ? {
          enabled: true,
          available: false,
          reason: reasons.disabled_by_zoom_tier,
          detail: fmt(reasons.requires_zoom_tier, {
            tier: graphZoomTierLabel(locale, GRAPH_THEME.effects.semanticRegions.minZoomTier),
          }),
        }
      : !analytics?.semanticRegions.ready
        ? {
            enabled: true,
            available: false,
            reason: analytics?.semanticRegions.reason ?? reasons.waiting_semantic_regions,
          }
        : { enabled: true, available: true, reason: analytics.semanticRegions.reason };

  const contours = !effectsState.contoursEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : isLayoutRunning
      ? { enabled: true, available: false, reason: layoutReason }
    : !contoursTierReady
      ? {
          enabled: true,
          available: false,
          reason: reasons.disabled_by_zoom_tier,
          detail: fmt(reasons.requires_zoom_tier, {
            tier: graphZoomTierLabel(locale, GRAPH_THEME.effects.contours.minZoomTier),
          }),
        }
      : !analytics?.centrality.ready
        ? {
            enabled: true,
            available: false,
            reason: analytics?.centrality.reason ?? reasons.waiting_centrality,
          }
        : { enabled: true, available: true, reason: analytics.centrality.reason };

  const pathfinding = !effectsState.pathfindingEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : !analytics?.directedPath.ready
      ? {
          enabled: true,
          available: false,
          reason: analytics?.directedPath.reason ?? reasons.waiting_traced_path,
        }
      : {
          enabled: true,
          available: true,
          reason: analytics.directedPath.verifiedAgainstActivePath
            ? reasons.pathfinding_ready_match
            : reasons.pathfinding_ready_differs,
        };

  const communities = !effectsState.communitiesEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : !analytics?.communities.ready
      ? {
          enabled: true,
          available: false,
          reason: analytics?.communities.reason ?? reasons.waiting_communities,
        }
      : {
          enabled: true,
          available: true,
          reason: analytics.communities.modularity !== null
            ? fmt(reasons.ready_modularity, {
                value: formatLocaleFixedDecimals(locale, analytics.communities.modularity, 3),
              })
            : analytics.communities.reason,
        };

  const centrality = !effectsState.centralityEnabled
    ? { enabled: false, available: false, reason: reasons.disabled_by_toggle }
    : !analytics?.centrality.ready
      ? {
          enabled: true,
          available: false,
          reason: analytics?.centrality.reason ?? reasons.waiting_centrality,
        }
      : { enabled: true, available: true, reason: analytics.centrality.reason };

  const legend = effectsState.legendEnabled
    ? { enabled: true, available: true, reason: reasons.panel_enabled }
    : { enabled: false, available: false, reason: reasons.disabled_by_toggle };

  // #1009: edge labels are immediately available once the graph is loaded —
  // they have no async analytics or zoom-tier dependency.
  const edgeLabels = effectsState.edgeLabelsEnabled
    ? { enabled: true, available: true, reason: reasons.ready }
    : { enabled: false, available: false, reason: reasons.disabled_by_toggle };

  const autoLayout = effectsState.autoLayoutEnabled
    ? {
        enabled: true,
        available: !isLayoutRunning,
        reason: isLayoutRunning ? reasons.layout_worker_running : reasons.auto_layout_ready_pause,
      }
    : { enabled: false, available: true, reason: reasons.seed_positions_manual };

  const diagnostics = !GRAPH_THEME.effects.diagnostics.enabledInDev
    ? { enabled: false, available: false, reason: reasons.disabled_in_production }
    : effectsState.diagnosticsEnabled
      ? { enabled: true, available: true, reason: reasons.ready }
      : { enabled: false, available: false, reason: reasons.disabled_by_toggle };

  return {
    pathPulse,
    pathFlow,
    lens,
    temporalEmphasis,
    semanticRegions,
    contours,
    pathfinding,
    communities,
    centrality,
    legend,
    edgeLabels,
    autoLayout,
    diagnostics,
  };
}

function drawGlowHalo(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  radius: number,
  color: string,
) {
  const gradient = context.createRadialGradient(x, y, 0, x, y, radius);
  gradient.addColorStop(0, color);
  gradient.addColorStop(1, "rgba(0,0,0,0)");
  context.fillStyle = gradient;
  context.beginPath();
  context.arc(x, y, radius, 0, Math.PI * 2);
  context.fill();
}

function drawNodeBadge(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  nodeRadius: number,
  badgeKind: GraphBadgeKind,
  badgeCount: number | undefined,
) {
  const badgeTheme = GRAPH_THEME.nodes.badges[badgeKind];
  const radius = GRAPH_THEME.nodes.badge.radius;
  const offset = GRAPH_THEME.nodes.badge.offset;
  const badgeX = x + Math.max(nodeRadius * 0.62, radius + offset);
  const badgeY = y - Math.max(nodeRadius * 0.62, radius + offset);

  drawGlowHalo(
    context,
    badgeX,
    badgeY,
    GRAPH_THEME.overlays.badgeGlowRadius,
    withAlpha(badgeTheme.color, GRAPH_THEME.nodes.badge.glowAlpha),
  );

  context.fillStyle = badgeTheme.color;
  context.beginPath();
  context.arc(badgeX, badgeY, radius, 0, Math.PI * 2);
  context.fill();

  context.strokeStyle = GRAPH_THEME.nodes.badge.stroke;
  context.lineWidth = 1;
  context.beginPath();
  context.arc(badgeX, badgeY, radius, 0, Math.PI * 2);
  context.stroke();

  context.fillStyle = GRAPH_THEME.nodes.badge.textColor;
  context.font = `700 ${GRAPH_THEME.nodes.badge.fontSize}px Inter, system-ui, sans-serif`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  const label = badgeKind === "provenance" && badgeCount && badgeCount > 1
    ? String(Math.min(9, badgeCount))
    : badgeTheme.label;
  context.fillText(label, badgeX, badgeY + 0.5);
}

type ReducerSceneState = {
  viewMode: GraphViewMode;
  zoomTier: GraphZoomTier;
  hoveredNodeId: string | null;
  selectedNodeId: string;
  selectedEdgeId: string;
  activePath: string[];
  activePathEdgeIds: string[];
  focusIds: Set<string>;
  edgeEndpointIds: Set<string>;
  pathNodeIds: Set<string>;
  pathEdgeIds: Set<string>;
  highlightedIncidentEdgeIds: Set<string>;
  overviewBackboneEdgeIds: Set<string>;
  distanceVisualState?: GraphDistanceVisualState;
  hiddenNodeTypes: ReadonlySet<string>;
  hiddenEdgeTypes: ReadonlySet<string>;
  keywordFilter: string;
  diffOverlay?: GraphDiffOverlayState | null;
};

const GRAPH_DIFF_ADDED_BORDER = "#5BC986";
const GRAPH_DIFF_MODIFIED_BORDER = "#8FE7FF";
const GRAPH_DIFF_DIM_ALPHA = 0.2;
const GRAPH_DIFF_ADDED_EDGE_COLOR = "#5BC986";
const GRAPH_DIFF_DIM_EDGE_ALPHA = 0.08;

const FULL_EDGE_CLASSES: GraphFullEdgeClass[] = [
  "hidden",
  "backbone",
  "bridge",
  "local-context",
  "selected",
  "path",
  "muted",
];

function createFullEdgeClassCounts(): GraphFullEdgeClassCounts {
  return FULL_EDGE_CLASSES.reduce((counts, edgeClass) => {
    counts[edgeClass] = 0;
    return counts;
  }, {} as GraphFullEdgeClassCounts);
}

function getIncidentEdgeRevealCap(viewMode: GraphViewMode, zoomTier: GraphZoomTier): number {
  return GRAPH_THEME.edges.contextCaps[viewMode]?.[zoomTier] ?? 0;
}

function scoreIncidentEdge(
  attrs: EdgeAttributes,
  edgeId: string,
  otherEndpointId: string,
  visibleNeighborIds: Set<string>,
  focusIds: Set<string>,
  pathEdgeIds: Set<string>,
  selectedEdgeId: string,
): number {
  if (pathEdgeIds.has(edgeId)) {
    return Number.POSITIVE_INFINITY;
  }
  if (selectedEdgeId && edgeId === selectedEdgeId) {
    return Number.POSITIVE_INFINITY;
  }

  const weight = Math.max(Number(attrs.weight ?? attrs.representativeWeight ?? 1) || 1, 1);
  const normalizedWeight = Math.min(1, Math.log1p(weight) / Math.log(25));
  const visualPriority = Math.max(0, Math.min(Number(attrs.visualPriority ?? 0), 1));
  const relationshipStrength = Math.max(0, Math.min(Number(attrs.relationshipStrength ?? 0), 1));

  return (visibleNeighborIds.has(otherEndpointId) ? 6 : 0)
    + (focusIds.has(otherEndpointId) ? 1.25 : 0)
    + visualPriority * 2
    + normalizedWeight * 1.4
    + relationshipStrength;
}

function buildHighlightedIncidentEdgeIds(
  displayGraph: GraphSceneGraph,
  interactionState: GraphInteractionState,
  displayState: GraphDisplayStateSnapshot | undefined,
  focusIds: Set<string>,
  pathEdgeIds: Set<string>,
): Set<string> {
  const primaryNodeId = interactionState.hoveredNodeId || interactionState.selectedNodeId;
  if (!primaryNodeId || !displayGraph.hasNode(primaryNodeId)) {
    return new Set();
  }

  const configuredCap = getIncidentEdgeRevealCap(interactionState.viewMode, interactionState.zoomTier);
  const cap = configuredCap > 0
    ? configuredCap
    : interactionState.zoomTier === "overview"
      ? 8
      : interactionState.zoomTier === "structure"
        ? 12
        : 24;

  const visibleNeighborIds = new Set(
    (displayState?.selectedVisibleNeighborIds ?? [])
      .filter((nodeId) => displayGraph.hasNode(nodeId)),
  );
  const candidates: Array<{ edgeId: string; score: number }> = [];

  displayGraph.edges(primaryNodeId).forEach((edge) => {
    const edgeId = String(edge);
    if (!displayGraph.hasEdge(edgeId)) {
      return;
    }
    const [source, target] = displayGraph.extremities(edgeId);
    const sourceId = String(source);
    const targetId = String(target);
    const otherEndpointId = sourceId === primaryNodeId ? targetId : sourceId;
    const attrs = displayGraph.getEdgeAttributes(edgeId) as EdgeAttributes;
    candidates.push({
      edgeId,
      score: scoreIncidentEdge(
        attrs,
        edgeId,
        otherEndpointId,
        visibleNeighborIds,
        focusIds,
        pathEdgeIds,
        interactionState.selectedEdgeId,
      ),
    });
  });

  candidates.sort((left, right) => {
    if (right.score !== left.score) {
      return right.score - left.score;
    }
    return left.edgeId.localeCompare(right.edgeId);
  });

  const selected = new Set<string>();
  candidates.forEach((candidate) => {
    if (
      candidate.edgeId === interactionState.selectedEdgeId
      || pathEdgeIds.has(candidate.edgeId)
      || selected.size < cap
    ) {
      selected.add(candidate.edgeId);
    }
  });
  return selected;
}

function buildReducerSceneState(
  displayGraph: GraphSceneGraph,
  interactionState: GraphInteractionState,
  displayState?: GraphDisplayStateSnapshot,
  analyticsSnapshot?: GraphAnalyticsSnapshot | null,
  distanceVisualState?: GraphDistanceVisualState,
  hiddenNodeTypes: ReadonlySet<string> = new Set(),
  hiddenEdgeTypes: ReadonlySet<string> = new Set(),
  keywordFilter: string = "",
  diffOverlay?: GraphDiffOverlayState | null,
): ReducerSceneState {
  const { viewMode, zoomTier, hoveredNodeId, selectedNodeId, selectedEdgeId, activePath } = interactionState;
  const primaryNodeId = hoveredNodeId || selectedNodeId;
  const focusIds = primaryNodeId && displayGraph.hasNode(primaryNodeId)
    ? buildFocusSetInGraph(displayGraph, primaryNodeId)
    : new Set<string>();
  const pathEdgeIds = buildPathEdgeSet(displayGraph, activePath, interactionState.activePathEdgeIds);

  return {
    viewMode,
    zoomTier,
    hoveredNodeId,
    selectedNodeId,
    selectedEdgeId,
    activePath,
    activePathEdgeIds: interactionState.activePathEdgeIds,
    focusIds,
    edgeEndpointIds: buildEdgeEndpointSet(displayGraph, selectedEdgeId),
    pathNodeIds: new Set(activePath),
    pathEdgeIds,
    overviewBackboneEdgeIds: new Set(analyticsSnapshot?.overviewBackbone.edgeIds ?? []),
    distanceVisualState,
    hiddenNodeTypes,
    hiddenEdgeTypes,
    keywordFilter,
    highlightedIncidentEdgeIds: buildHighlightedIncidentEdgeIds(
      displayGraph,
      interactionState,
      displayState,
      focusIds,
      pathEdgeIds,
    ),
    diffOverlay,
  };
}

function applyGraphDiffOverlayStyle(
  nodeId: string,
  overlay: GraphDiffOverlayState,
  resolvedStyle: ReturnType<typeof resolveNodeElementStyle>,
  data: Record<string, unknown>,
) {
  if (!overlay.enabled) {
    return null;
  }
  const change = overlay.added.has(nodeId)
    ? "added"
    : overlay.modified.has(nodeId)
      ? "modified"
      : null;
  const isFocus = overlay.focusNodeId === nodeId;
  if (!change) {
    return {
      ...data,
      color: withAlpha(String(resolvedStyle.color), GRAPH_DIFF_DIM_ALPHA),
      shellColor: withAlpha(String(resolvedStyle.shellColor ?? resolvedStyle.color), GRAPH_DIFF_DIM_ALPHA),
      borderColor: withAlpha(String(resolvedStyle.borderColor), 0.12),
      borderSize: Math.max(0.5, (resolvedStyle.borderSize ?? 1) * 0.6),
      forceLabel: false,
      label: undefined,
      zIndex: 0,
    };
  }
  const borderColor = change === "added" ? GRAPH_DIFF_ADDED_BORDER : GRAPH_DIFF_MODIFIED_BORDER;
  return {
    ...data,
    color: resolvedStyle.color,
    shellColor: resolvedStyle.shellColor,
    borderColor,
    borderSize: isFocus ? 3.5 : 2.5,
    ringColor: isFocus ? borderColor : resolvedStyle.ringColor,
    ringSize: isFocus ? 5 : resolvedStyle.ringSize,
    zIndex: (resolvedStyle.zIndex ?? 1) + (isFocus ? 40 : 8),
    forceLabel: isFocus ? true : resolvedStyle.forceLabel,
    label: isFocus ? resolvedStyle.label : resolvedStyle.label,
  };
}

function getFullGraphEdgeClass(
  displayGraph: GraphSceneGraph,
  edgeId: string,
  currentState: ReducerSceneState,
): GraphFullEdgeClass {
  if (!displayGraph.hasEdge(edgeId)) {
    return "hidden";
  }

  const [source, target] = displayGraph.extremities(edgeId);
  const sourceId = String(source);
  const targetId = String(target);
  const sourceAttrs = displayGraph.hasNode(sourceId)
    ? displayGraph.getNodeAttributes(sourceId) as NodeAttributes
    : undefined;
  const targetAttrs = displayGraph.hasNode(targetId)
    ? displayGraph.getNodeAttributes(targetId) as NodeAttributes
    : undefined;

  return classifyFullGraphEdge(
    edgeId,
    sourceId,
    targetId,
    currentState.zoomTier,
    currentState.hoveredNodeId,
    currentState.selectedNodeId,
    currentState.selectedEdgeId,
    currentState.focusIds,
    currentState.pathEdgeIds,
    currentState.highlightedIncidentEdgeIds,
    currentState.overviewBackboneEdgeIds,
    sourceAttrs,
    targetAttrs,
  );
}

function buildFullGraphEdgeClassDiagnostics(
  displayGraph: GraphSceneGraph,
  currentState: ReducerSceneState,
): GraphFullEdgeClassDiagnostics {
  const counts = createFullEdgeClassCounts();

  displayGraph.forEachEdge((edgeId) => {
    const edgeClass = currentState.viewMode === "full"
      ? getFullGraphEdgeClass(displayGraph, String(edgeId), currentState)
      : "hidden";
    counts[edgeClass] += 1;
  });

  return {
    mode: currentState.viewMode,
    zoomTier: currentState.zoomTier,
    totalEdges: displayGraph.size,
    visibleEdges: displayGraph.size - counts.hidden,
    counts,
    updatedAt: Date.now(),
  };
}

function applySceneState(
  sigma: Sigma,
  reducerSceneStateRef: { current: ReducerSceneState },
  reducerWarningStateRef: { current: { missingEdges: Set<string>; missingNodes: Set<string> } },
  refreshTargets?: {
    nodes?: string[];
    edges?: string[];
  },
) {
  sigma.setSetting("nodeReducer", (node, data) => {
    const currentGraph = sigma.getGraph() as GraphSceneGraph;
    const currentState = reducerSceneStateRef.current;
    const cameraRatio = sigma.getCamera().getState().ratio;
    if (!currentGraph.hasNode(node)) {
      if (!reducerWarningStateRef.current.missingNodes.has(node)) {
        reducerWarningStateRef.current.missingNodes.add(node);
        debugGraphRuntime("node-reducer-node-missing", {
          nodeId: node,
          order: currentGraph.order,
          size: currentGraph.size,
        });
      }
      return {
        ...data,
        hidden: true,
      };
    }
    const attrs = data as NodeAttributes;
    const state = resolveNodeVisualState(
      node,
      currentState.zoomTier,
      currentState.hoveredNodeId,
      currentState.selectedNodeId,
      currentState.selectedEdgeId,
      currentState.focusIds,
      currentState.edgeEndpointIds,
      currentState.pathNodeIds,
    );
    const style = resolveNodeElementStyle(
      GRAPH_THEME,
      currentState.zoomTier,
      state,
      attrs,
      data.label,
      cameraRatio,
    );
    const distanceStyle = currentState.viewMode === "full"
      ? resolveDistanceNodeStyle(
        GRAPH_THEME,
        currentState.zoomTier,
        style,
        currentState.distanceVisualState,
        String(node),
      )
      : {};
    const resolvedStyle = { ...style, ...distanceStyle };
    const typeHidden = Boolean(attrs.hidden) || isNodeTypeSuppressed(attrs.nodeType, currentState.hiddenNodeTypes);
    const keywordHidden = isNodeKeywordSuppressed(attrs, String(node), currentState.keywordFilter);
    const diffOverlay = currentState.diffOverlay;
    const diffStyled = diffOverlay?.enabled && !typeHidden && !keywordHidden
      ? applyGraphDiffOverlayStyle(String(node), diffOverlay, resolvedStyle, data as Record<string, unknown>)
      : null;

      return diffStyled ?? {
        ...data,
        color: resolvedStyle.color,
        shellColor: resolvedStyle.shellColor,
        coreScale: resolvedStyle.coreScale,
        size: resolvedStyle.size,
        forceLabel: typeHidden || keywordHidden ? false : resolvedStyle.forceLabel,
        label: typeHidden || keywordHidden ? undefined : resolvedStyle.label,
        suppressNodeChip: state === "hovered",
        zIndex: resolvedStyle.zIndex,
        hidden: typeHidden || keywordHidden || resolvedStyle.hidden,
        borderColor: resolvedStyle.borderColor,
        borderSize: resolvedStyle.borderSize,
        ringColor: resolvedStyle.showRing ? resolvedStyle.ringColor : resolvedStyle.borderColor,
        ringSize: resolvedStyle.ringSize,
        entityShape: resolvedStyle.entityShape,
        entityShapeKind: resolvedStyle.entityShapeKind,
        entityAspectRatio: resolvedStyle.entityAspectRatio,
      };
    });

  sigma.setSetting("edgeReducer", (edge, data) => {
    const currentGraph = sigma.getGraph() as GraphSceneGraph;
    const currentState = reducerSceneStateRef.current;
    if (!currentGraph.hasEdge(edge)) {
      if (!reducerWarningStateRef.current.missingEdges.has(edge)) {
        reducerWarningStateRef.current.missingEdges.add(edge);
        debugGraphRuntime("edge-reducer-edge-missing", {
          edgeId: edge,
          order: currentGraph.order,
          size: currentGraph.size,
        });
      }
      return {
        ...data,
        hidden: true,
      };
    }
    const attrs = data as EdgeAttributes;
    const [source, target] = currentGraph.extremities(edge);
    const stableEdgeId = String(edge);
    const hasActiveInteraction = Boolean(
      currentState.hoveredNodeId
      || currentState.selectedNodeId
      || currentState.selectedEdgeId
      || currentState.pathEdgeIds.size > 0,
    );
    const fullEdgeClass = currentState.viewMode === "full"
      ? getFullGraphEdgeClass(currentGraph, stableEdgeId, currentState)
      : undefined;
    const state = currentState.viewMode === "full"
      ? mapFullEdgeClassToVisualState(
        fullEdgeClass ?? "hidden",
        {
          hoveredNodeId: currentState.hoveredNodeId,
          hasActiveInteraction,
        },
      )
      : resolveEdgeVisualState(
        stableEdgeId,
        String(source),
        String(target),
        currentState.zoomTier,
        currentState.hoveredNodeId,
        currentState.selectedNodeId,
        currentState.selectedEdgeId,
        currentState.focusIds,
        currentState.pathEdgeIds,
        currentState.highlightedIncidentEdgeIds,
      );
    const style = resolveEdgeElementStyle(
      GRAPH_THEME,
      currentState.zoomTier,
      state,
      attrs,
      source,
      target,
      currentState.viewMode,
      stableEdgeId,
      fullEdgeClass,
    );
    const distanceStyle = currentState.viewMode === "full"
      ? resolveDistanceEdgeStyle(
        style,
        currentState.distanceVisualState,
        String(source),
        String(target),
        fullEdgeClass,
      )
      : {};
    const resolvedStyle = { ...style, ...distanceStyle };
    const sourceAttrs = currentGraph.hasNode(source)
      ? currentGraph.getNodeAttributes(source) as NodeAttributes
      : undefined;
    const targetAttrs = currentGraph.hasNode(target)
      ? currentGraph.getNodeAttributes(target) as NodeAttributes
      : undefined;
    const endpointHidden = Boolean(sourceAttrs?.hidden || targetAttrs?.hidden)
      || isNodeTypeSuppressed(sourceAttrs?.nodeType, currentState.hiddenNodeTypes)
      || isNodeTypeSuppressed(targetAttrs?.nodeType, currentState.hiddenNodeTypes)
      || (sourceAttrs && isNodeKeywordSuppressed(sourceAttrs, String(source), currentState.keywordFilter))
      || (targetAttrs && isNodeKeywordSuppressed(targetAttrs, String(target), currentState.keywordFilter))
      || isEdgeTypeSuppressed(edgeTypeOf(attrs), currentState.hiddenEdgeTypes);

    const diffOverlay = currentState.diffOverlay;
    let diffEdgeColor = resolvedStyle.color;
    let diffEdgeSize = resolvedStyle.size;
    let diffEdgeZIndex = resolvedStyle.zIndex;
    if (diffOverlay?.enabled && !endpointHidden && !resolvedStyle.hidden) {
      const sourceId = String(source);
      const targetId = String(target);
      const edgeType = String(attrs.edgeType ?? attrs.type ?? "");
      const edgeKey = graphDiffEdgeKey(sourceId, targetId, edgeType);
      const isAddedEdge = diffOverlay.addedEdgeKeys.has(edgeKey);
      const touchesChange = graphDiffEdgeTouchesChange(sourceId, targetId, diffOverlay);
      if (isAddedEdge) {
        diffEdgeColor = GRAPH_DIFF_ADDED_EDGE_COLOR;
        diffEdgeSize = Math.max(resolvedStyle.size ?? 1, 2.2);
        diffEdgeZIndex = (resolvedStyle.zIndex ?? 1) + 6;
      } else if (!touchesChange) {
        diffEdgeColor = withAlpha(String(resolvedStyle.color), GRAPH_DIFF_DIM_EDGE_ALPHA);
        diffEdgeSize = Math.max(0.35, (resolvedStyle.size ?? 1) * 0.45);
        diffEdgeZIndex = 0;
      }
    }

    return {
      ...data,
      hidden: endpointHidden || resolvedStyle.hidden,
      type: resolvedStyle.type,
      color: diffEdgeColor,
      size: diffEdgeSize,
      zIndex: diffEdgeZIndex,
      curvature: resolvedStyle.curvature,
      // #1009: Sigma's edge label renderer draws data.label — the graph
      // stores the relationship type in edgeType, which the renderer never
      // saw, so enabling renderEdgeLabels alone left edges blank.
      // Use || rather than ?? so that an empty-string edgeType (possible
      // when the API returns type: "") does not produce a blank label.
      label: endpointHidden || resolvedStyle.hidden ? undefined : String(attrs.edgeType || data.label || ""),
      labelColor: endpointHidden || resolvedStyle.hidden ? undefined : resolvedStyle.labelColor,
    };
  });

  if ((refreshTargets?.nodes?.length ?? 0) > 0 || (refreshTargets?.edges?.length ?? 0) > 0) {
    sigma.scheduleRefresh({
      partialGraph: {
        nodes: refreshTargets?.nodes,
        edges: refreshTargets?.edges,
      },
    });
    return;
  }

  sigma.scheduleRefresh();
}

function dispatchBehaviorAction(
  behaviors: GraphBehavior[],
  context: GraphBehaviorContext,
  action: GraphBehaviorActionRequest,
) {
  for (const behavior of behaviors) {
    if (behavior.performAction?.(context, action)) {
      return;
    }
  }
}

export const GraphCanvas = forwardRef<GraphCanvasHandle, GraphCanvasProps>(
  function GraphCanvas(
    {
      graphVersion,
      graphReady,
      displayGraph,
      displayMeta,
      displayState,
      onNodeClick,
      onEdgeClick,
      selectedNodeId,
      focusedNodeId,
      selectedEdgeId,
      activePath = [],
      activePathEdgeIds = [],
      distanceVisualState,
      effectsState,
      temporalState,
      isLayoutRunning,
      onLayoutRunningChange,
      viewMode,
      className,
      showFitViewButton = true,
      pluginOverlays = [],
      onSceneRuntimeChange,
      onInteractionStateChange,
      onCameraStateChange,
      onDiagnosticsChange,
      onAnalyticsChange,
      locale = "en",
      hiddenNodeTypes = [],
      hiddenEdgeTypes = [],
      keywordFilter = "",
      diffOverlay = null,
    },
    ref,
  ) {
    const effectReasons = useMemo(
      () => graphEffectReasonsCopy(locale),
      [locale],
    );
    const containerRef = useRef<HTMLDivElement>(null);
    const overlayRef = useRef<HTMLCanvasElement>(null);
    const structureLayerCanvasRef = useRef<HTMLCanvasElement | null>(null);
    const structureLayerCacheRef = useRef<GraphStructureCurveCache | null>(null);
    const structureLayerLastDrawAtRef = useRef<number | null>(null);
    const structureLayerDiagnosticsRef = useRef<GraphStructureLayerDiagnostics | null>(null);
    const sigmaRef = useRef<Sigma | null>(null);
    const fa2Ref = useRef<FA2Layout | null>(null);
    const behaviorContextRef = useRef<GraphBehaviorContext | null>(null);
    const runtimeRef = useRef<GraphSceneRuntime | null>(null);
    const sigmaResizeObserverRef = useRef<ResizeObserver | null>(null);
    const sigmaCameraSyncRef = useRef<(() => void) | null>(null);
    const displayGraphRef = useRef<GraphSceneGraph>(displayGraph);
    const displayStateRef = useRef(displayState);
    const displayMetaRef = useRef(displayMeta);
    const graphVersionRef = useRef(graphVersion);
    const selectedNodeIdRef = useRef(selectedNodeId);
    const focusedNodeIdRef = useRef(focusedNodeId);
    const distanceVisualStateRef = useRef(distanceVisualState);
    const viewModeRef = useRef(viewMode);
    const onNodeClickRef = useRef(onNodeClick);
    const onEdgeClickRef = useRef(onEdgeClick);
    const onSceneRuntimeChangeRef = useRef(onSceneRuntimeChange);
    const onCameraStateChangeRef = useRef(onCameraStateChange);
    // #1009: tracked as a ref so the Sigma creation effect always reads the
    // current value without needing effectsState in its dependency array.
    const effectsStateRef = useRef(effectsState);
    const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
    const [zoomTier, setZoomTier] = useState<GraphZoomTier>("overview");
    const [analyticsSnapshot, setAnalyticsSnapshot] = useState<GraphAnalyticsSnapshot | null>(null);
    const [layoutSettledEpoch, setLayoutSettledEpoch] = useState(0);
    const appliedGraphVersionRef = useRef<number | null>(null);
    const fittedDisplaySignatureRef = useRef<DisplayFitSignature | null>(null);
    const layoutSyncFrameRef = useRef<number | null>(null);
    const layoutSyncTickRef = useRef(0);
    const deferredFocusFrameRef = useRef<number | null>(null);
    const fullGraphLayoutSettleTimeoutRef = useRef<number | null>(null);
    const groupedLayoutSettleTimeoutRef = useRef<number | null>(null);
    const overlayRedrawRef = useRef<(() => void) | null>(null);
    const reducerWarningStateRef = useRef<{ missingEdges: Set<string>; missingNodes: Set<string> }>({
      missingEdges: new Set<string>(),
      missingNodes: new Set<string>(),
    });

    displayGraphRef.current = displayGraph;
    displayStateRef.current = displayState;
    displayMetaRef.current = displayMeta;
    graphVersionRef.current = graphVersion;
    selectedNodeIdRef.current = selectedNodeId;
    focusedNodeIdRef.current = focusedNodeId;
    distanceVisualStateRef.current = distanceVisualState;
    viewModeRef.current = viewMode;
    onNodeClickRef.current = onNodeClick;
    onEdgeClickRef.current = onEdgeClick;
    onSceneRuntimeChangeRef.current = onSceneRuntimeChange;
    onCameraStateChangeRef.current = onCameraStateChange;
    effectsStateRef.current = effectsState;

    const behaviors = useMemo<GraphBehavior[]>(
      () => [
        hoverActivationBehavior,
        clickSelectionBehavior,
        focusCameraBehavior,
        createSearchFocusBehavior(),
        createPathHighlightBehavior(),
        fitViewBehavior,
        createViewModeSwitchBehavior(),
      ],
      [],
    );

    const interactionState = useMemo(
      () => createInteractionState(
        hoveredNodeId,
        selectedNodeId,
        focusedNodeId,
        selectedEdgeId,
        activePath,
        activePathEdgeIds,
        viewMode,
        zoomTier,
        isLayoutRunning,
      ),
      [
        activePath,
        activePathEdgeIds,
        focusedNodeId,
        hoveredNodeId,
        isLayoutRunning,
        selectedEdgeId,
        selectedNodeId,
        viewMode,
        zoomTier,
      ],
    );
    const interactionStateRef = useRef<GraphInteractionState>(interactionState);
    interactionStateRef.current = interactionState;
    const previousInteractionStateRef = useRef<GraphInteractionState | null>(null);
    const previousDistanceVisualStateRef = useRef<GraphDistanceVisualState | undefined>(undefined);
    useEffect(() => {
      if (!isLayoutRunning) {
        setLayoutSettledEpoch((epoch) => epoch + 1);
      }
    }, [displayGraph, graphVersion, isLayoutRunning]);

    const shouldComputeCommunities = effectsState.communitiesEnabled || effectsState.semanticRegionsEnabled;
    const shouldComputeCentrality = effectsState.centralityEnabled || effectsState.semanticRegionsEnabled || effectsState.contoursEnabled;
    const analyticsBase = useMemo(
      () => computeGraphAnalyticsBase(displayGraph, {
        computeCommunities: shouldComputeCommunities,
        computeCentrality: shouldComputeCentrality,
      }),
      [displayGraph, shouldComputeCentrality, shouldComputeCommunities],
    );
    const hiddenNodeTypeSet = useMemo(
      () => new Set(hiddenNodeTypes),
      [hiddenNodeTypes],
    );
    const hiddenEdgeTypeSet = useMemo(
      () => new Set(hiddenEdgeTypes),
      [hiddenEdgeTypes],
    );
    const normalizedKeywordFilter = useMemo(
      () => normalizeKeywordFilter(keywordFilter),
      [keywordFilter],
    );
    const reducerSceneState = useMemo(
      () => buildReducerSceneState(
        displayGraph,
        interactionState,
        displayState,
        analyticsSnapshot,
        distanceVisualState,
        hiddenNodeTypeSet,
        hiddenEdgeTypeSet,
        normalizedKeywordFilter,
        diffOverlay,
      ),
      [analyticsSnapshot, diffOverlay, displayGraph, displayState, distanceVisualState, hiddenEdgeTypeSet, hiddenNodeTypeSet, interactionState, normalizedKeywordFilter],
    );
    const reducerSceneStateRef = useRef<ReducerSceneState>(reducerSceneState);
    reducerSceneStateRef.current = reducerSceneState;
    const edgeClassDiagnostics = useMemo(
      () => buildFullGraphEdgeClassDiagnostics(displayGraph, reducerSceneState),
      [displayGraph, reducerSceneState],
    );
    const structureLayerGate = useMemo(
      () => evaluateGraphStructureLayerGate({
        mode: GRAPH_THEME.edges.fullGraphStructureLayer.mode,
        viewMode,
        isLayoutRunning,
        edgeDiagnostics: edgeClassDiagnostics,
        minimumLiteralEdges: GRAPH_THEME.edges.fullGraphStructureLayer.minimumLiteralEdges,
      }),
      [edgeClassDiagnostics, isLayoutRunning, viewMode],
    );
    const structureLayerCache = useMemo(() => {
      if (!structureLayerGate.enabled) {
        return null;
      }
      const cacheKey = createGraphStructureCacheKey({
        graphVersion,
        zoomTier,
        layoutSettledEpoch,
        overviewBackboneEdgeIds: reducerSceneState.overviewBackboneEdgeIds,
      });
      return buildGraphStructureCurveCache({
        graphRef: displayGraph,
        cacheKey,
        classifyEdge: (edgeId) => getFullGraphEdgeClass(displayGraph, edgeId, reducerSceneState),
        maxCurves: GRAPH_THEME.edges.fullGraphStructureLayer.maxCurves,
        curveStrength: GRAPH_THEME.edges.fullGraphStructureLayer.curveStrength,
      });
    }, [displayGraph, graphVersion, layoutSettledEpoch, reducerSceneState, structureLayerGate.enabled, zoomTier]);
    structureLayerCacheRef.current = structureLayerCache;
    const structureLayerDiagnostics = useMemo(
      () => getGraphStructureLayerDiagnostics({
        gate: structureLayerGate,
        cache: structureLayerCache,
        minimumCurves: GRAPH_THEME.edges.fullGraphStructureLayer.minimumCurves,
        canvasAvailable: Boolean(structureLayerCanvasRef.current),
        lastDrawAt: structureLayerLastDrawAtRef.current,
      }),
      [structureLayerCache, structureLayerGate],
    );
    structureLayerDiagnosticsRef.current = structureLayerDiagnostics;
    const displayFitSignature = useMemo<DisplayFitSignature>(() => ({
      graphVersion,
      viewMode,
      layoutMode: displayMeta.layoutMode,
      displayGraph,
    }), [displayGraph, displayMeta.layoutMode, graphVersion, viewMode]);

    const animateCameraToBounds = useCallback((
      intent: "fit-display-graph" | "fit-selection-context" | "fit-focused-graph",
      targetBounds: SigmaCustomBBox | null,
      diagnostics?: Record<string, unknown>,
    ) => {
      const sigma = sigmaRef.current;
      if (!sigma) {
        return;
      }

      if (sigma.getCustomBBox()) {
        sigma.setCustomBBox(null);
      }

      const container = containerRef.current;
      const dimensions = sigma.getDimensions();
      const currentCameraState = sigma.getCamera().getState();
      const target = targetBounds
        ? computeCameraTargetFromBounds(sigma, targetBounds)
        : {
            x: 0.5,
            y: 0.5,
            ratio: 1,
            angle: currentCameraState.angle,
          };
      if (!target) {
        debugGraphRuntime("camera-fit-target-invalid", {
          intent,
          graphVersion: graphVersionRef.current,
          viewMode: viewModeRef.current,
          order: displayGraphRef.current.order,
          size: displayGraphRef.current.size,
          boundsX: targetBounds?.x ?? null,
          boundsY: targetBounds?.y ?? null,
          ...diagnostics,
        });
        return;
      }

      debugGraphRuntime("camera-fit-target", {
        intent,
        graphVersion: graphVersionRef.current,
        viewMode: viewModeRef.current,
        order: displayGraphRef.current.order,
        size: displayGraphRef.current.size,
        selectionPreserved: Boolean(selectedNodeIdRef.current),
        containerWidth: container?.clientWidth ?? dimensions.width,
        containerHeight: container?.clientHeight ?? dimensions.height,
        targetX: target.x,
        targetY: target.y,
        targetRatio: target.ratio,
        boundsX: targetBounds?.x ?? null,
        boundsY: targetBounds?.y ?? null,
        ...diagnostics,
      });

      void sigma.getCamera().animate(
        target,
        { duration: GRAPH_THEME.motion.cameraMs, easing: "quadraticOut" },
      );
    }, []);

    const fitDisplayGraphInView = useCallback(() => {
      const sigma = sigmaRef.current;
      if (!sigma) {
        return;
      }

      const bounds = computeDisplayedGraphBounds(sigma, displayGraphRef.current);
      if (!bounds) {
        debugGraphRuntime("camera-fit-display-graph-fallback", {
          graphVersion: graphVersionRef.current,
          viewMode: viewModeRef.current,
          reason: "display-bounds-unavailable",
          order: displayGraphRef.current.order,
          size: displayGraphRef.current.size,
        });
        animateCameraToBounds("fit-display-graph", null, {
          fallback: "reset-empty-bounds",
        });
        return;
      }

      const displayBBox = expandGraphSpaceBounds(bounds, bounds, {
        paddingRatio: 0.14,
        minSpanRatio: 0.02,
        minSpanFloor: 0.04,
      });
      animateCameraToBounds("fit-display-graph", displayBBox, {
        boundsCount: bounds.count,
        minX: bounds.minX,
        maxX: bounds.maxX,
        minY: bounds.minY,
        maxY: bounds.maxY,
      });
    }, [animateCameraToBounds]);

    const centerSelectionInView = useCallback(function centerSelectionInViewInternal(nodeId: string, attempt = 0) {
      const sigma = sigmaRef.current;
      if (!sigma) {
        return;
      }

      const currentDisplayGraph = displayGraphRef.current;
      const selectionNodeIds = collectSelectionContextNodeIds(
        currentDisplayGraph,
        displayStateRef.current,
        nodeId,
      );
      if (selectionNodeIds.length === 0) {
        debugGraphRuntime("camera-selection-missing-node", {
          nodeId,
          graphVersion: graphVersionRef.current,
          viewMode: viewModeRef.current,
        });
        return;
      }

      const selectedDisplayNodeId = selectionNodeIds[0];
      const selectedDisplayData = sigma.getNodeDisplayData(selectedDisplayNodeId);
      if (selectedDisplayData) {
        const viewportPoint = sigma.framedGraphToViewport({
          x: selectedDisplayData.x,
          y: selectedDisplayData.y,
        });
        const dimensions = sigma.getDimensions();
        if (isPointNearViewport(viewportPoint, dimensions.width, dimensions.height, 96)) {
          debugGraphRuntime("camera-selection-visible-noop", {
            nodeId,
            selectedDisplayNodeId,
            graphVersion: graphVersionRef.current,
            viewMode: viewModeRef.current,
            viewportX: viewportPoint.x,
            viewportY: viewportPoint.y,
          });
          sigma.scheduleRefresh();
          return;
        }
      }

      const bounds = computeDisplayedNodeBounds(sigma, selectionNodeIds);
      if (!bounds) {
        if (attempt < 3) {
          debugGraphRuntime("camera-selection-display-bounds-deferred", {
            nodeId,
            graphVersion: graphVersionRef.current,
            attempt: attempt + 1,
            viewMode: viewModeRef.current,
            contextCount: selectionNodeIds.length,
          });
          if (deferredFocusFrameRef.current !== null) {
            window.cancelAnimationFrame(deferredFocusFrameRef.current);
          }
          deferredFocusFrameRef.current = window.requestAnimationFrame(() => {
            deferredFocusFrameRef.current = null;
            centerSelectionInViewInternal(nodeId, attempt + 1);
          });
        } else {
          debugGraphRuntime("camera-selection-display-bounds-fallback-fit", {
            nodeId,
            graphVersion: graphVersionRef.current,
            viewMode: viewModeRef.current,
            contextCount: selectionNodeIds.length,
          });
        }
        return;
      }

      const camera = sigma.getCamera();
      const currentCameraState = camera.getState();
      const target = {
        x: (bounds.minX + bounds.maxX) / 2,
        y: (bounds.minY + bounds.maxY) / 2,
        ratio: currentCameraState.ratio,
        angle: currentCameraState.angle,
      };

      debugGraphRuntime("camera-selection-gentle-center", {
        nodeId,
        contextCount: bounds.count,
        boundsSource: "displayed-selection-context",
        minX: bounds.minX,
        maxX: bounds.maxX,
        minY: bounds.minY,
        maxY: bounds.maxY,
        targetX: target.x,
        targetY: target.y,
        preservedRatio: target.ratio,
      });

      void camera.animate(
        target,
        { duration: GRAPH_THEME.motion.cameraMs, easing: "quadraticOut" },
      );
    }, []);

    const centerGroupedSelectionInView = useCallback((nodeId: string) => {
      const sigma = sigmaRef.current;
      if (!sigma) {
        return;
      }

      const currentDisplayGraph = displayGraphRef.current;
      const selectionNodeIds = collectSelectionContextNodeIds(
        currentDisplayGraph,
        displayStateRef.current,
        nodeId,
      );
      if (selectionNodeIds.length === 0) {
        debugGraphRuntime("camera-grouped-selection-missing-node", {
          nodeId,
          graphVersion: graphVersionRef.current,
          viewMode: viewModeRef.current,
        });
        return;
      }

      const bounds = computeDisplayedNodeBounds(sigma, selectionNodeIds);
      if (!bounds) {
        debugGraphRuntime("camera-grouped-selection-display-bounds-missing", {
          nodeId,
          graphVersion: graphVersionRef.current,
          viewMode: viewModeRef.current,
          contextCount: selectionNodeIds.length,
        });
        return;
      }

      const camera = sigma.getCamera();
      const currentCameraState = camera.getState();
      const target = {
        x: (bounds.minX + bounds.maxX) / 2,
        y: (bounds.minY + bounds.maxY) / 2,
        ratio: currentCameraState.ratio,
        angle: currentCameraState.angle,
      };

      debugGraphRuntime("camera-grouped-selection-center", {
        nodeId,
        graphVersion: graphVersionRef.current,
        viewMode: viewModeRef.current,
        contextCount: bounds.count,
        targetX: target.x,
        targetY: target.y,
        preservedRatio: target.ratio,
      });

      void camera.animate(
        target,
        { duration: GRAPH_THEME.motion.cameraMs, easing: "quadraticOut" },
      );
    }, []);

    const focusNodeInView = useCallback((nodeId: string) => {
      const sigma = sigmaRef.current;
      if (!sigma) {
        return;
      }

      const focusedView = viewModeRef.current === "focused"
        && Boolean(selectedNodeIdRef.current)
        && graph.hasNode(selectedNodeIdRef.current);
      if (focusedView) {
        const focusedBounds = computeDisplayedGraphBounds(sigma, displayGraphRef.current);
        const focusedBBox = focusedBounds
          ? expandGraphSpaceBounds(focusedBounds, focusedBounds, {
              paddingRatio: 0.14,
              minSpanRatio: 0.08,
              minSpanFloor: 0.02,
            })
          : null;
        animateCameraToBounds("fit-focused-graph", focusedBBox, {
          nodeId,
          focusedCount: focusedBounds?.count ?? 0,
          focusedMinX: focusedBounds?.minX ?? null,
          focusedMaxX: focusedBounds?.maxX ?? null,
          focusedMinY: focusedBounds?.minY ?? null,
          focusedMaxY: focusedBounds?.maxY ?? null,
        });
        return;
      }

      centerSelectionInView(nodeId);
    }, [animateCameraToBounds, centerSelectionInView]);

    const fitCurrentView = useCallback(() => {
      fitDisplayGraphInView();
    }, [fitDisplayGraphInView]);

    const dispatchAction = useCallback((action: GraphBehaviorActionRequest) => {
      const context = behaviorContextRef.current;
      if (!context) {
        return;
      }

      dispatchBehaviorAction(behaviors, context, action);
    }, [behaviors]);

    const getBehaviorContext = useCallback((sigma?: Sigma | null): GraphBehaviorContext | null => {
      const runtimeSigma = sigma ?? sigmaRef.current;
      if (!runtimeSigma) {
        return null;
      }

      const context: GraphBehaviorContext = {
        sigma: runtimeSigma,
        graph,
        displayGraph: displayGraphRef.current,
        getInteractionState: () => interactionStateRef.current,
        setHoveredNodeId,
        onNodeSelectionChange: (nodeId: string) => onNodeClickRef.current(nodeId),
        onEdgeSelectionChange: (edgeId: string) => onEdgeClickRef.current?.(edgeId),
        focusNodeInView,
        centerSelectionInView,
        centerGroupedSelectionInView,
        fitCurrentView,
        dispatchAction,
      };
      behaviorContextRef.current = context;
      return context;
    }, [centerGroupedSelectionInView, centerSelectionInView, dispatchAction, fitCurrentView, focusNodeInView]);

    const dispatchToBehaviors = useCallback((
      hook: "onNodeEnter" | "onNodeLeave" | "onNodeClick" | "onEdgeClick" | "onStageClick" | "onCameraChange",
      ...args: unknown[]
    ) => {
      const context = getBehaviorContext();
      if (!context) {
        return;
      }

      for (const behavior of behaviors) {
        const handler = behavior[hook];
        if (typeof handler === "function") {
          (handler as (...handlerArgs: unknown[]) => void)(context, ...args);
        }
      }
    }, [behaviors, getBehaviorContext]);

    useImperativeHandle(ref, () => ({
      fitView: () => dispatchAction({ type: "fitView" }),
      focusNode: (nodeId: string) => dispatchAction({ type: "focusNode", nodeId }),
      zoomIn: () => {
        const sigma = sigmaRef.current;
        if (!sigma) {
          return;
        }
        debugGraphRuntime("camera-zoom-in", {
          graphVersion: graphVersionRef.current,
          ratioBefore: sigma.getCamera().getState().ratio,
        });
        sigma.getCamera().animatedZoom({ duration: GRAPH_THEME.motion.cameraMs });
      },
      zoomOut: () => {
        const sigma = sigmaRef.current;
        if (!sigma) {
          return;
        }
        debugGraphRuntime("camera-zoom-out", {
          graphVersion: graphVersionRef.current,
          ratioBefore: sigma.getCamera().getState().ratio,
        });
        sigma.getCamera().animatedUnzoom({ duration: GRAPH_THEME.motion.cameraMs });
      },
      requestRender: () => sigmaRef.current?.scheduleRefresh(),
      getCameraState: () => {
        const sigma = sigmaRef.current;
        if (!sigma) {
          return null;
        }
        const state = sigma.getCamera().getState();
        return { x: state.x, y: state.y, ratio: state.ratio };
      },
    }), [dispatchAction]);

    const syncCameraState = useCallback((sigma: Sigma) => {
      const camera = sigma.getCamera();
      const state = camera.getState();
      const cameraState: GraphCameraState = {
        x: state.x,
        y: state.y,
        ratio: state.ratio,
      };
      const nextTier = getZoomTier(cameraState.ratio);
      setZoomTier((current) => (current === nextTier ? current : nextTier));
      onCameraStateChangeRef.current?.(cameraState);
      dispatchToBehaviors("onCameraChange", cameraState);
      debugGraphRuntime("camera-updated", {
        graphVersion: graphVersionRef.current,
        ratio: cameraState.ratio,
      });
    }, [dispatchToBehaviors]);

    useEffect(() => {
      if (!graphReady || sigmaRef.current || !containerRef.current) {
        return;
      }

      const sigma = new Sigma(displayGraphRef.current, containerRef.current, buildSigmaSettings(
        effectsStateRef.current.edgeLabelsEnabled,
      ));
      applySigmaCanvasThemeSettings(sigma);
      sigmaRef.current = sigma;
      appliedGraphVersionRef.current = graphVersionRef.current;

      const camera = sigma.getCamera();
      const runtime: GraphSceneRuntime = {
        renderer: "sigma",
        scene: sigma,
        graph,
        displayGraph: displayGraphRef.current,
        graphVersion: graphVersionRef.current,
        layoutMode: displayMetaRef.current.layoutMode,
        requestRender: () => sigma.scheduleRefresh(),
        getCameraState: () => {
          const state = camera.getState();
          return { x: state.x, y: state.y, ratio: state.ratio };
        },
      };
      runtimeRef.current = runtime;
      onSceneRuntimeChangeRef.current?.(runtime);
      debugGraphRuntime("sigma-created", {
        graphVersion: graphVersionRef.current,
        layoutMode: displayMetaRef.current.layoutMode,
        order: displayGraphRef.current.order,
        size: displayGraphRef.current.size,
      });

      const context = getBehaviorContext(sigma);
      if (context) {
        for (const behavior of behaviors) {
          behavior.attach(context);
        }
      }

      const handleResize = () => {
        if (containerRef.current && containerRef.current.offsetWidth > 0) {
          sigma.scheduleRefresh();
        }
      };

      const resizeObserver = new ResizeObserver(handleResize);
      resizeObserver.observe(containerRef.current);
      sigmaResizeObserverRef.current = resizeObserver;

      const handleCameraUpdated = () => syncCameraState(sigma);
      sigmaCameraSyncRef.current = handleCameraUpdated;
      camera.on("updated", handleCameraUpdated);
      sigma.on("clickNode", ({ node }) => dispatchToBehaviors("onNodeClick", node));
      sigma.on("clickEdge", ({ edge }) => {
        const currentDisplayGraph = displayGraphRef.current;
        const [source, target] = currentDisplayGraph.extremities(edge);
        const stableEdgeId = String(edge);
        const attrs = currentDisplayGraph.getEdgeAttributes(edge) as EdgeAttributes;

        if (isEdgeInteractable(currentDisplayGraph, interactionStateRef.current, stableEdgeId, source, target, attrs)) {
          dispatchToBehaviors("onEdgeClick", stableEdgeId);
        }
      });
      sigma.on("clickStage", () => dispatchToBehaviors("onStageClick"));
      sigma.on("enterNode", ({ node }) => dispatchToBehaviors("onNodeEnter", node));
      sigma.on("leaveNode", ({ node }) => dispatchToBehaviors("onNodeLeave", node));
      sigma.on("enterEdge", ({ edge }) => {
        const container = containerRef.current;
        if (!container) {
          return;
        }

        const currentDisplayGraph = displayGraphRef.current;
        const [source, target] = currentDisplayGraph.extremities(edge);
        const stableEdgeId = String(edge);
        const attrs = currentDisplayGraph.getEdgeAttributes(edge) as EdgeAttributes;
        container.style.cursor = isEdgeInteractable(currentDisplayGraph, interactionStateRef.current, stableEdgeId, source, target, attrs)
          ? "pointer"
          : "";
      });
      sigma.on("leaveEdge", () => {
        if (containerRef.current) {
          containerRef.current.style.cursor = "";
        }
      });

      try {
        const structureCanvas = sigma.createCanvas("structure", {
          beforeLayer: "nodes",
          afterLayer: "edges",
          style: {
            pointerEvents: "none",
          },
        });
        structureLayerCanvasRef.current = structureCanvas;
      } catch (error) {
        debugGraphRuntime("structure-layer-create-failed", {
          error: error instanceof Error ? error.message : String(error),
        });
        structureLayerCanvasRef.current = null;
      }

      requestAnimationFrame(() => {
        syncCameraState(sigma);
      });
    }, [behaviors, dispatchToBehaviors, getBehaviorContext, graphReady, syncCameraState]);

    // #1009: renderEdgeLabels follows the Effects-panel toggle instead of
    // staying hardcoded — dense graphs get their label-free edges back.
    useEffect(() => {
      const sigma = sigmaRef.current;
      if (!sigma) {
        return;
      }
      sigma.setSetting("renderEdgeLabels", effectsState.edgeLabelsEnabled);
      sigma.scheduleRefresh();
    }, [effectsState.edgeLabelsEnabled]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      if (!graphReady || !sigma) {
        return;
      }
      applySigmaCanvasThemeSettings(sigma);
      sigma.scheduleRefresh();
    }, [graphReady, graphVersion]);

    useEffect(() => {
      return () => {
        const sigma = sigmaRef.current;
        const context = behaviorContextRef.current;
        if (context) {
          for (const behavior of behaviors) {
            behavior.detach(context);
          }
        }
        if (containerRef.current) {
          containerRef.current.style.cursor = "";
        }
        sigmaResizeObserverRef.current?.disconnect();
        sigmaResizeObserverRef.current = null;
        if (sigma && sigmaCameraSyncRef.current) {
          sigma.getCamera().off("updated", sigmaCameraSyncRef.current);
        }
        sigmaCameraSyncRef.current = null;
        if (sigma) {
          debugGraphRuntime("sigma-killed", {
            graphVersion: graphVersionRef.current,
          });
          if (structureLayerCanvasRef.current) {
            try {
              sigma.killLayer("structure");
            } catch {
              // Sigma.kill() also cleans layers; ignore if already removed.
            }
          }
          structureLayerCanvasRef.current = null;
          sigma.kill();
        }
        if (deferredFocusFrameRef.current !== null) {
          window.cancelAnimationFrame(deferredFocusFrameRef.current);
          deferredFocusFrameRef.current = null;
        }
        runtimeRef.current = null;
        behaviorContextRef.current = null;
        sigmaRef.current = null;
        onSceneRuntimeChangeRef.current?.(null);
      };
    }, [behaviors]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      if (!graphReady || !sigma) {
        return;
      }

      if (appliedGraphVersionRef.current === graphVersion && sigma.getGraph() === displayGraph) {
        return;
      }

      debugGraphRuntime("sigma-set-graph", {
        graphVersion,
        displayFitViewMode: displayFitSignature.viewMode,
        displayFitLayoutMode: displayFitSignature.layoutMode,
        layoutMode: displayMeta.layoutMode,
        order: displayGraph.order,
        size: displayGraph.size,
      });
      if (deferredFocusFrameRef.current !== null) {
        window.cancelAnimationFrame(deferredFocusFrameRef.current);
        deferredFocusFrameRef.current = null;
      }
      reducerWarningStateRef.current.missingEdges.clear();
      reducerWarningStateRef.current.missingNodes.clear();
      sigma.setCustomBBox(null);
      sigma.setGraph(displayGraph);
      appliedGraphVersionRef.current = graphVersion;
      fittedDisplaySignatureRef.current = null;
      previousInteractionStateRef.current = null;
      previousDistanceVisualStateRef.current = undefined;
      behaviorContextRef.current = getBehaviorContext(sigma);
      if (runtimeRef.current) {
        runtimeRef.current.displayGraph = displayGraph;
        runtimeRef.current.graphVersion = graphVersion;
        runtimeRef.current.layoutMode = displayMeta.layoutMode;
      }
      sigma.scheduleRefresh();
    }, [displayFitSignature.layoutMode, displayFitSignature.viewMode, displayGraph, displayMeta.layoutMode, getBehaviorContext, graphReady, graphVersion]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      if (!graphReady || !sigma || isSameDisplayFitSignature(fittedDisplaySignatureRef.current, displayFitSignature)) {
        return;
      }

      const frame = window.requestAnimationFrame(() => {
        if (
          !sigmaRef.current
          || graphVersionRef.current !== graphVersion
          || displayGraphRef.current !== displayFitSignature.displayGraph
          || viewModeRef.current !== displayFitSignature.viewMode
          || displayMetaRef.current.layoutMode !== displayFitSignature.layoutMode
        ) {
          return;
        }

        fittedDisplaySignatureRef.current = displayFitSignature;
        debugGraphRuntime("display-fit-signature-applied", {
          graphVersion: displayFitSignature.graphVersion,
          viewMode: displayFitSignature.viewMode,
          layoutMode: displayFitSignature.layoutMode,
          order: displayFitSignature.displayGraph.order,
          size: displayFitSignature.displayGraph.size,
        });
        if (focusedNodeIdRef.current && viewModeRef.current === "focused") {
          debugGraphRuntime("initial-focused-fit", {
            graphVersion,
            nodeId: focusedNodeIdRef.current,
          });
          focusNodeInView(focusedNodeIdRef.current);
          return;
        }

        debugGraphRuntime("initial-fit-view", {
          graphVersion,
          selectedNodeId: selectedNodeIdRef.current || null,
          viewMode: viewModeRef.current,
        });
        dispatchAction({ type: "fitView" });
      });

      return () => {
        window.cancelAnimationFrame(frame);
      };
    }, [centerSelectionInView, dispatchAction, displayFitSignature, focusNodeInView, graphReady, graphVersion]);

    useEffect(() => {
      const context = getBehaviorContext();
      if (!context) {
        return;
      }

      for (const behavior of behaviors) {
        behavior.onStateChange?.(context, interactionState);
      }

      for (const behavior of behaviors) {
        behavior.apply?.(context, interactionState);
      }
      onInteractionStateChange?.(interactionState);
    }, [behaviors, getBehaviorContext, interactionState, onInteractionStateChange]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      const container = containerRef.current;
      if (!sigma || !container) {
        setAnalyticsSnapshot(null);
        onAnalyticsChange?.(null);
        return;
      }

      const visibleNodes = collectVisibleNodeSamples(
        sigma,
        displayGraph,
        container.clientWidth,
        container.clientHeight,
      ).map((sample) => sample.nodeId);

      const analytics = buildGraphAnalyticsSnapshot({
        graphRef: displayGraph,
        interactionState,
        base: analyticsBase,
        visibleNodeIds: visibleNodes,
        locale,
      });
      setAnalyticsSnapshot(analytics);
      onAnalyticsChange?.(analytics);
    }, [analyticsBase, displayGraph, interactionState, locale, onAnalyticsChange]);

    useEffect(() => {
      if (!onDiagnosticsChange) {
        return;
      }

      const sigma = sigmaRef.current;
      const container = containerRef.current;
      const availability = buildEffectAvailability(
        effectReasons,
        locale,
        interactionState,
        effectsState,
        temporalState,
        analyticsSnapshot,
        isLayoutRunning,
        sigma,
        container?.clientWidth ?? 0,
        container?.clientHeight ?? 0,
      );
      onDiagnosticsChange({
        effectAvailability: availability,
        edgeClasses: edgeClassDiagnostics,
        structureLayer: structureLayerDiagnosticsRef.current ?? structureLayerDiagnostics,
        distanceVisual: distanceVisualStateRef.current,
      });
      if (import.meta.env.DEV && effectsState.diagnosticsEnabled) {
        console.debug("[Edge Truth]", edgeClassDiagnostics);
      }
    }, [
      analyticsSnapshot,
      edgeClassDiagnostics,
      effectReasons,
      effectsState,
      interactionState,
      isLayoutRunning,
      onDiagnosticsChange,
      structureLayerDiagnostics,
      temporalState,
      distanceVisualState,
      locale,
    ]);

    useEffect(() => {
      previousInteractionStateRef.current = null;
      previousDistanceVisualStateRef.current = undefined;
    }, [displayGraph]);

    const hiddenNodeTypeKey = `${hiddenNodeTypes.join("\0")}\u0001${hiddenEdgeTypes.join("\0")}\u0002${normalizedKeywordFilter}`;
    const previousHiddenNodeTypeKeyRef = useRef(hiddenNodeTypeKey);
    useEffect(() => {
      const sigma = sigmaRef.current;
      if (!sigma) {
        return;
      }

      const previousInteractionState = previousInteractionStateRef.current;
      const distanceVisualStateChanged = previousDistanceVisualStateRef.current !== distanceVisualState;
      const typeFilterChanged = previousHiddenNodeTypeKeyRef.current !== hiddenNodeTypeKey;
      const refreshTargets = !distanceVisualStateChanged && !typeFilterChanged && previousInteractionState
        ? collectInteractionRefreshTargets(displayGraph, previousInteractionState, interactionState)
        : undefined;

      applySceneState(sigma, reducerSceneStateRef, reducerWarningStateRef, refreshTargets);
      previousInteractionStateRef.current = interactionState;
      previousDistanceVisualStateRef.current = distanceVisualState;
      previousHiddenNodeTypeKeyRef.current = hiddenNodeTypeKey;
      overlayRedrawRef.current?.();
    }, [displayGraph, distanceVisualState, hiddenNodeTypeKey, interactionState, reducerSceneStateRef]);

    const drawStructureLayerFrame = useCallback(() => {
      const sigma = sigmaRef.current;
      const canvas = structureLayerCanvasRef.current;
      const cache = structureLayerCacheRef.current;
      const diagnostics = getGraphStructureLayerDiagnostics({
        gate: structureLayerGate,
        cache,
        minimumCurves: GRAPH_THEME.edges.fullGraphStructureLayer.minimumCurves,
        canvasAvailable: Boolean(canvas),
        lastDrawAt: structureLayerLastDrawAtRef.current,
      });
      structureLayerDiagnosticsRef.current = diagnostics;

      if (!sigma || !canvas || !diagnostics.enabled || !cache) {
        clearGraphStructureLayer(canvas);
        return;
      }

      const drawn = drawGraphStructureLayer({
        sigma,
        canvas,
        cache,
      });
      if (drawn) {
        structureLayerLastDrawAtRef.current = Date.now();
        structureLayerDiagnosticsRef.current = {
          ...diagnostics,
          lastDrawAt: structureLayerLastDrawAtRef.current,
        };
      }
    }, [structureLayerGate]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      if (!graphReady || !sigma) {
        return;
      }

      const draw = () => drawStructureLayerFrame();
      sigma.on("afterRender", draw);
      draw();

      return () => {
        sigma.off("afterRender", draw);
      };
    }, [drawStructureLayerFrame, graphReady, structureLayerCache]);

    useEffect(() => {
      if (isLayoutRunning || viewMode !== "full") {
        clearGraphStructureLayer(structureLayerCanvasRef.current);
      }
    }, [isLayoutRunning, viewMode]);

    const drawOverlayFrame = useCallback(() => {
      const sigma = sigmaRef.current;
      const overlay = overlayRef.current;
      const container = containerRef.current;
      if (!sigma || !overlay || !container) {
        return false;
      }

      const { width: viewportWidth, height: viewportHeight } = syncGraphOverlayCanvas(overlay, sigma);
      const pixelRatio = window.devicePixelRatio || 1;

      const context = overlay.getContext("2d");
      if (!context) {
        return false;
      }

      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      context.clearRect(0, 0, viewportWidth, viewportHeight);

      const primaryNodeId = interactionState.hoveredNodeId || interactionState.selectedNodeId;
      const focusIds = primaryNodeId && displayGraph.hasNode(primaryNodeId)
        ? buildFocusSetInGraph(displayGraph, primaryNodeId)
        : new Set<string>();
      const edgeEndpointIds = buildEdgeEndpointSet(displayGraph, interactionState.selectedEdgeId);
      const pathNodeIds = new Set(interactionState.activePath);
      const pathSegments = collectPathSegments(
        sigma,
        interactionState.activePath,
        interactionState.activePathEdgeIds,
        interactionState.zoomTier,
        viewportWidth,
        viewportHeight,
      );
      const visibleNodeSamples = collectVisibleNodeSamples(sigma, displayGraph, viewportWidth, viewportHeight);
      const effectAvailability = buildEffectAvailability(
        effectReasons,
        locale,
        interactionState,
        effectsState,
        temporalState,
        analyticsSnapshot,
        isLayoutRunning,
        sigma,
        viewportWidth,
        viewportHeight,
      );
      const cameraRatio = sigma.getCamera().getState().ratio;
      const nodesToDecorate = new Set<string>([
        ...focusIds,
        ...edgeEndpointIds,
        ...pathNodeIds,
        ...(primaryNodeId ? [primaryNodeId] : []),
      ]);
      const lensFocusIds = new Set<string>();
      if (primaryNodeId) {
        reducerSceneStateRef.current.highlightedIncidentEdgeIds.forEach((edgeId) => {
          if (!displayGraph.hasEdge(edgeId)) {
            return;
          }
          const [source, target] = displayGraph.extremities(edgeId);
          const otherEndpointId = String(source) === primaryNodeId ? String(target) : String(source);
          if (displayGraph.hasNode(otherEndpointId)) {
            lensFocusIds.add(otherEndpointId);
          }
        });
      }
      const now = performance.now() / 1000;

      if (!isLayoutRunning) {
        drawContourLayer(context, analyticsSnapshot, visibleNodeSamples, interactionState, effectsState);
        drawSemanticRegionsLayer(context, analyticsSnapshot, visibleNodeSamples, interactionState, effectsState);
        drawTemporalEmphasisLayer(context, visibleNodeSamples, temporalState, interactionState, effectsState);
      }

      nodesToDecorate.forEach((nodeId) => {
        const displayData = sigma.getNodeDisplayData(nodeId);
        if (!displayData) return;
        if (!displayGraph.hasNode(nodeId)) {
          debugGraphRuntime("overlay-node-missing-from-display-graph", {
            nodeId,
            graphVersion: graphVersionRef.current,
            viewMode: viewModeRef.current,
          });
          return;
        }
        const attrs = displayGraph.getNodeAttributes(nodeId) as NodeAttributes;
        const state = resolveNodeVisualState(
          nodeId,
          interactionState.zoomTier,
          interactionState.hoveredNodeId,
          interactionState.selectedNodeId,
          interactionState.selectedEdgeId,
          focusIds,
          edgeEndpointIds,
          pathNodeIds,
        );
        const style = resolveNodeElementStyle(
          GRAPH_THEME,
          interactionState.zoomTier,
          state,
          attrs,
          attrs.label,
          cameraRatio,
        );
        const point = getNodeViewportPoint(sigma, nodeId);
        if (!point) {
          return;
        }
        if (style.showHalo) {
          const viewportSize = getViewportNodeSize(sigma, displayData.size);
          const radius = Math.max(
            viewportSize * GRAPH_THEME.overlays.glowRadiusMultiplier * (style.nodeVariant === "selected" ? 1.08 : 1),
            GRAPH_THEME.overlays.minGlowRadius,
          );
          drawGlowHalo(
            context,
            point.x,
            point.y,
            radius,
            withAlpha(
              style.haloColor,
              nodeId === primaryNodeId ? GRAPH_THEME.overlays.hoverGlowAlpha : GRAPH_THEME.overlays.pathGlowAlpha,
            ),
          );
        }

        if (style.showBadge && style.badgeKind) {
          drawNodeBadge(
            context,
            point.x,
            point.y,
            getViewportNodeSize(sigma, displayData.size),
            style.badgeKind,
            style.badgeCount,
          );
        }
      });

      if (
        !isLayoutRunning
        && !interactionState.hoveredNodeId
        && interactionState.selectedNodeId
        && effectAvailability.lens.available
      ) {
        drawLensLayer(context, sigma, interactionState.selectedNodeId, lensFocusIds);
      }

      drawPathEffectsLayer(context, pathSegments, effectsState, effectAvailability, now);
      return effectAvailability.pathPulse.available || effectAvailability.pathFlow.available;
    }, [
      analyticsSnapshot,
      displayGraph,
      effectReasons,
      effectsState,
      interactionState,
      isLayoutRunning,
      temporalState,
    ]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      const container = containerRef.current;
      if (!graphReady || !sigma || !container) {
        return;
      }

      let frame = 0;
      let disposed = false;

      const render = () => {
        if (disposed) {
          return;
        }

        const animated = drawOverlayFrame();
        if (animated) {
          frame = window.requestAnimationFrame(render);
        } else {
          frame = 0;
        }
      };

      const redrawStatic = () => {
        if (frame !== 0) {
          return;
        }
        drawOverlayFrame();
      };
      overlayRedrawRef.current = redrawStatic;

      const camera = sigma.getCamera();
      const resizeObserver = new ResizeObserver(redrawStatic);
      resizeObserver.observe(container);
      camera.on("updated", redrawStatic);
      // Keep canvas halos aligned with WebGL nodes after layout ticks and container resizes.
      sigma.on("afterRender", redrawStatic);

      render();
      return () => {
        disposed = true;
        overlayRedrawRef.current = null;
        resizeObserver.disconnect();
        camera.off("updated", redrawStatic);
        sigma.off("afterRender", redrawStatic);
        if (frame !== 0) {
          window.cancelAnimationFrame(frame);
        }
      };
    }, [drawOverlayFrame, graphReady]);

    useEffect(() => {
      const sigma = sigmaRef.current;
      const layoutTargetGraph = displayMeta.layoutMode === "owned" ? displayGraph : graph;
      const usingGroupedOwnedLayout = displayMeta.layoutMode === "owned" && viewMode === "grouped";
      const targetKey = displayMeta.layoutMode === "owned"
        ? `display:${graphVersion}:${viewMode}`
        : `store:${displayMeta.layoutMode}`;
      const currentTargetKey = (fa2Ref.current as (FA2Layout & { __targetKey?: string }) | null)?.__targetKey;

      if (!isLayoutRunning) {
        fa2Ref.current?.stop();
        if (fullGraphLayoutSettleTimeoutRef.current !== null) {
          window.clearTimeout(fullGraphLayoutSettleTimeoutRef.current);
          fullGraphLayoutSettleTimeoutRef.current = null;
        }
        if (groupedLayoutSettleTimeoutRef.current !== null) {
          window.clearTimeout(groupedLayoutSettleTimeoutRef.current);
          groupedLayoutSettleTimeoutRef.current = null;
        }
        if (layoutSyncFrameRef.current !== null) {
          window.cancelAnimationFrame(layoutSyncFrameRef.current);
          layoutSyncFrameRef.current = null;
        }
        return;
      }

      if (!fa2Ref.current || currentTargetKey !== targetKey) {
        fa2Ref.current?.kill();
        const nextLayout = new FA2Layout(
          layoutTargetGraph,
          usingGroupedOwnedLayout ? GROUPED_FA2_SETTINGS : FA2_SETTINGS,
        ) as FA2Layout & { __targetKey?: string };
        nextLayout.__targetKey = targetKey;
        fa2Ref.current = nextLayout;
        debugGraphRuntime("layout-target-changed", {
          graphVersion,
          layoutMode: displayMeta.layoutMode,
          target: displayMeta.layoutMode === "owned" ? "display-owned" : displayMeta.layoutMode === "base" ? "base" : "store-for-mirror",
          order: layoutTargetGraph.order,
          size: layoutTargetGraph.size,
        });
      }

      fa2Ref.current.start();

      if (groupedLayoutSettleTimeoutRef.current !== null) {
        window.clearTimeout(groupedLayoutSettleTimeoutRef.current);
        groupedLayoutSettleTimeoutRef.current = null;
      }
      if (fullGraphLayoutSettleTimeoutRef.current !== null) {
        window.clearTimeout(fullGraphLayoutSettleTimeoutRef.current);
        fullGraphLayoutSettleTimeoutRef.current = null;
      }

      if (usingGroupedOwnedLayout) {
        groupedLayoutSettleTimeoutRef.current = window.setTimeout(() => {
          fa2Ref.current?.stop();
          groupedLayoutSettleTimeoutRef.current = null;
          onLayoutRunningChange?.(false);
          debugGraphRuntime("grouped-layout-auto-settled", {
            graphVersion: graphVersionRef.current,
            viewMode: viewModeRef.current,
            order: displayGraphRef.current.order,
            size: displayGraphRef.current.size,
          });
        }, GRAPH_THEME.grouped.layout.settleMs);
      } else {
        fullGraphLayoutSettleTimeoutRef.current = window.setTimeout(() => {
          fa2Ref.current?.stop();
          fullGraphLayoutSettleTimeoutRef.current = null;
          onLayoutRunningChange?.(false);
          debugGraphRuntime("full-layout-auto-settled", {
            graphVersion: graphVersionRef.current,
            viewMode: viewModeRef.current,
            layoutMode: displayMetaRef.current.layoutMode,
            order: displayGraphRef.current.order,
            size: displayGraphRef.current.size,
          });
        }, FULL_GRAPH_LAYOUT_SETTLE_MS);
      }

      if (displayMeta.layoutMode === "mirrored" && sigma) {
        let disposed = false;

        const syncTick = () => {
          if (disposed || !sigmaRef.current || !isLayoutRunning) {
            return;
          }

          const changed = syncDisplayNodePositionsFromStore(displayGraphRef.current, graph);
          if (changed > 0) {
            sigmaRef.current.scheduleRefresh();
            layoutSyncTickRef.current += 1;
            if (layoutSyncTickRef.current === 1 || layoutSyncTickRef.current % 30 === 0) {
              debugGraphRuntime("layout-mirror-sync", {
                graphVersion: graphVersionRef.current,
                changedNodes: changed,
                tick: layoutSyncTickRef.current,
              });
            }
          }

          layoutSyncFrameRef.current = window.requestAnimationFrame(syncTick);
        };

        layoutSyncTickRef.current = 0;
        layoutSyncFrameRef.current = window.requestAnimationFrame(syncTick);

        return () => {
          disposed = true;
          if (fullGraphLayoutSettleTimeoutRef.current !== null) {
            window.clearTimeout(fullGraphLayoutSettleTimeoutRef.current);
            fullGraphLayoutSettleTimeoutRef.current = null;
          }
          if (groupedLayoutSettleTimeoutRef.current !== null) {
            window.clearTimeout(groupedLayoutSettleTimeoutRef.current);
            groupedLayoutSettleTimeoutRef.current = null;
          }
          if (layoutSyncFrameRef.current !== null) {
            window.cancelAnimationFrame(layoutSyncFrameRef.current);
            layoutSyncFrameRef.current = null;
          }
          fa2Ref.current?.stop();
        };
      }

      return () => {
        if (fullGraphLayoutSettleTimeoutRef.current !== null) {
          window.clearTimeout(fullGraphLayoutSettleTimeoutRef.current);
          fullGraphLayoutSettleTimeoutRef.current = null;
        }
        if (groupedLayoutSettleTimeoutRef.current !== null) {
          window.clearTimeout(groupedLayoutSettleTimeoutRef.current);
          groupedLayoutSettleTimeoutRef.current = null;
        }
        fa2Ref.current?.stop();
      };
    }, [displayGraph, displayMeta.layoutMode, graphVersion, isLayoutRunning, viewMode]);

    useEffect(() => {
      return () => {
        if (fullGraphLayoutSettleTimeoutRef.current !== null) {
          window.clearTimeout(fullGraphLayoutSettleTimeoutRef.current);
          fullGraphLayoutSettleTimeoutRef.current = null;
        }
        if (groupedLayoutSettleTimeoutRef.current !== null) {
          window.clearTimeout(groupedLayoutSettleTimeoutRef.current);
          groupedLayoutSettleTimeoutRef.current = null;
        }
        if (layoutSyncFrameRef.current !== null) {
          window.cancelAnimationFrame(layoutSyncFrameRef.current);
          layoutSyncFrameRef.current = null;
        }
        fa2Ref.current?.kill();
        fa2Ref.current = null;
      };
    }, []);

    const handleFitView = useCallback(() => {
      fitCurrentView();
    }, [fitCurrentView]);

    return (
      <div
        className={graphCanvasRoot}
        data-testid={diffOverlay?.enabled ? "workspace-graph-diff-overlay-active" : undefined}
      >
        <div ref={containerRef} className={cn(graphCanvasHost, className)} />
        <canvas ref={overlayRef} className={graphCanvasOverlay} />
        {pluginOverlays.length ? (
          <div className={graphPluginOverlayLayer}>
            {pluginOverlays.map((overlay, index) => (
              <div key={`graph-plugin-overlay-${index}`} className={graphPluginOverlaySlot}>
                {overlay}
              </div>
            ))}
          </div>
        ) : null}
        {showFitViewButton ? (
          <Button id="graph-fit-view-btn" type="button" variant="secondary" size="sm" onClick={handleFitView} className={graphFitViewBtn}>
            Fit View
          </Button>
        ) : null}
      </div>
    );
  }
);
