/**
 * Maps Basis `styles.css` design tokens onto Explorer `GRAPH_THEME` for Sigma/canvas code.
 * Explorer has no separate product theme in Basis — call `syncBasisGraphTheme` before graph UI paints.
 */
import type { Theme } from '@/lib/shell/theme.js';

import { GRAPH_THEME } from '@/lib/workspace/graphTheme.js';

function readCssVarRgb(property: 'color' | 'background-color', cssVar: string): string {
  const probe = document.createElement('span');
  probe.style.setProperty(property, `var(${cssVar})`);
  probe.style.position = 'absolute';
  probe.style.visibility = 'hidden';
  probe.style.pointerEvents = 'none';
  document.documentElement.appendChild(probe);
  const value = getComputedStyle(probe)[property === 'color' ? 'color' : 'backgroundColor'];
  document.documentElement.removeChild(probe);
  return value;
}

function colorToRgb(color: string): { r: number; g: number; b: number } {
  const match = color.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  if (match) {
    return {
      r: Number.parseInt(match[1], 10),
      g: Number.parseInt(match[2], 10),
      b: Number.parseInt(match[3], 10),
    };
  }

  const canvas = document.createElement('canvas');
  canvas.width = 1;
  canvas.height = 1;
  const context = canvas.getContext('2d');
  if (!context) {
    return { r: 120, g: 113, b: 107 };
  }
  context.clearRect(0, 0, 1, 1);
  context.fillStyle = color;
  context.fillRect(0, 0, 1, 1);
  const [r, g, b] = context.getImageData(0, 0, 1, 1).data;
  return { r, g, b };
}

function rgbCss(color: string): string {
  const { r, g, b } = colorToRgb(color);
  return `rgb(${r}, ${g}, ${b})`;
}

function rgbaFromRgb(rgb: string, alpha: number): string {
  const { r, g, b } = colorToRgb(rgb);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function mixRgbCss(base: string, mix: string, baseWeight: number): string {
  const weight = Math.min(1, Math.max(0, baseWeight));
  const a = colorToRgb(base);
  const b = colorToRgb(mix);
  const channel = (left: number, right: number) => Math.round(left * weight + right * (1 - weight));
  return `rgb(${channel(a.r, b.r)}, ${channel(a.g, b.g)}, ${channel(a.b, b.b)})`;
}

const DARK_ZOOM_TIER_EDGES = {
  overview: { edgePriorityThreshold: 0.72, edgeSizeScale: 0.62 },
  structure: { edgePriorityThreshold: 0.4, edgeSizeScale: 0.92 },
  inspection: { edgePriorityThreshold: 0, edgeSizeScale: 1.18 },
} as const;

const DARK_DEFAULT_EDGE_STATE = { minSize: 0.2, sizeMultiplier: 0.48 };

function applyZoomTierEdgeLod(
  tiers: typeof DARK_ZOOM_TIER_EDGES,
  defaultEdgeState: typeof DARK_DEFAULT_EDGE_STATE,
): void {
  GRAPH_THEME.zoomTiers.overview.edgePriorityThreshold = tiers.overview.edgePriorityThreshold;
  GRAPH_THEME.zoomTiers.overview.edgeSizeScale = tiers.overview.edgeSizeScale;
  GRAPH_THEME.zoomTiers.structure.edgePriorityThreshold = tiers.structure.edgePriorityThreshold;
  GRAPH_THEME.zoomTiers.structure.edgeSizeScale = tiers.structure.edgeSizeScale;
  GRAPH_THEME.zoomTiers.inspection.edgePriorityThreshold = tiers.inspection.edgePriorityThreshold;
  GRAPH_THEME.zoomTiers.inspection.edgeSizeScale = tiers.inspection.edgeSizeScale;
  GRAPH_THEME.edges.states.default.minSize = defaultEdgeState.minSize;
  GRAPH_THEME.edges.states.default.sizeMultiplier = defaultEdgeState.sizeMultiplier;
}

/** Explorer LOD alphas were tuned for dark canvas; light backgrounds need stronger strokes. */
function applyCanvasEdgeVisibility(isDark: boolean): void {
  const full = GRAPH_THEME.edges.visibility.full;
  const structure = GRAPH_THEME.edges.fullGraphStructure;

  if (isDark) {
    GRAPH_THEME.canvas.hideNonBackboneEdgesAtOverview = true;
    applyZoomTierEdgeLod(DARK_ZOOM_TIER_EDGES, DARK_DEFAULT_EDGE_STATE);
    GRAPH_THEME.edges.contextCaps.full.overview = 0;
    GRAPH_THEME.edges.contextCaps.full.structure = 12;
    GRAPH_THEME.edges.contextCaps.full.inspection = 24;
    GRAPH_THEME.interaction.localContextAlpha = 0.32;
    GRAPH_THEME.interaction.hoverContextAlpha = 0.32;
    GRAPH_THEME.interaction.selectedEdgeAlpha = 0.6;
    GRAPH_THEME.interaction.localContextMaxSize = 0.6;
    GRAPH_THEME.interaction.selectedEdgeMaxSize = 1;
    GRAPH_THEME.interaction.smallGraphDefaultEdgeAlpha = 0.1;
    GRAPH_THEME.interaction.smallGraphContextEdgeAlpha = 0.22;

    full.overview.backgroundSampleRate = 0.035;
    full.overview.defaultPriorityThreshold = 0.96;
    full.overview.hideMuted = true;
    full.overview.inactiveAlpha = 0.005;
    full.structure.backgroundSampleRate = 0.16;
    full.structure.defaultPriorityThreshold = 0.82;
    full.structure.hideMuted = true;
    full.inspection.backgroundSampleRate = 0.28;
    full.inspection.defaultPriorityThreshold = 0.72;
    full.inspection.hideMuted = true;

    structure.structureEdgeAlpha = 0.042;
    structure.inspectionEdgeAlpha = 0.036;
    structure.backboneAlpha = 0.032;
    structure.ambientBackboneAlpha = 0.042;
    structure.bridgeAlpha = 0.048;

    full.overview.defaultAlpha = 0.008;
    full.structure.defaultAlpha = 0.013;
    full.inspection.defaultAlpha = 0.018;
    return;
  }

  // Match semantica Explorer LOD/caps (same as dark); only raise alphas for light canvas contrast.
  GRAPH_THEME.canvas.hideNonBackboneEdgesAtOverview = true;
  applyZoomTierEdgeLod(DARK_ZOOM_TIER_EDGES, DARK_DEFAULT_EDGE_STATE);
  GRAPH_THEME.edges.contextCaps.full.overview = 0;
  GRAPH_THEME.edges.contextCaps.full.structure = 12;
  GRAPH_THEME.edges.contextCaps.full.inspection = 24;
  GRAPH_THEME.interaction.localContextAlpha = 0.72;
  GRAPH_THEME.interaction.hoverContextAlpha = 0.72;
  GRAPH_THEME.interaction.selectedEdgeAlpha = 0.68;
  GRAPH_THEME.interaction.localContextMaxSize = 0.85;
  GRAPH_THEME.interaction.selectedEdgeMaxSize = 1.1;
  GRAPH_THEME.interaction.smallGraphDefaultEdgeAlpha = 0.46;
  GRAPH_THEME.interaction.smallGraphContextEdgeAlpha = 0.62;

  full.overview.defaultAlpha = 0.11;
  full.overview.backgroundSampleRate = 0.035;
  full.overview.defaultPriorityThreshold = 0.96;
  full.overview.hideMuted = true;
  full.overview.inactiveAlpha = 0.08;
  full.overview.mutedAlpha = 0.18;
  full.overview.neighborAlpha = 0.22;
  full.structure.defaultAlpha = 0.24;
  full.structure.backgroundSampleRate = 0.16;
  full.structure.defaultPriorityThreshold = 0.82;
  full.structure.hideMuted = true;
  full.structure.mutedAlpha = 0.2;
  full.structure.neighborAlpha = 0.26;
  full.inspection.defaultAlpha = 0.3;
  full.inspection.backgroundSampleRate = 0.28;
  full.inspection.defaultPriorityThreshold = 0.72;
  full.inspection.hideMuted = true;
  full.inspection.mutedAlpha = 0.24;
  full.inspection.neighborAlpha = 0.3;

  structure.structureEdgeAlpha = 0.26;
  structure.inspectionEdgeAlpha = 0.3;
  structure.backboneAlpha = 0.22;
  structure.ambientBackboneAlpha = 0.2;
  structure.bridgeAlpha = 0.24;
}

/** Align Explorer graph chrome + canvas tokens with Basis `styles.css` theme. */
export function syncBasisGraphTheme(mode: Theme): void {
  const background = readCssVarRgb('background-color', '--background');
  const card = readCssVarRgb('background-color', '--card');
  const muted = readCssVarRgb('background-color', '--muted');
  const foreground = readCssVarRgb('color', '--foreground');
  const mutedForeground = readCssVarRgb('color', '--muted-foreground');
  const border = readCssVarRgb('background-color', '--border');
  const primary = readCssVarRgb('color', '--primary');
  const brand = readCssVarRgb('color', '--brand-primary');
  const signal = readCssVarRgb('color', '--signal');
  const ok = readCssVarRgb('color', '--ok');
  const warn = readCssVarRgb('color', '--warn');
  const info = readCssVarRgb('color', '--info');
  const destructive = readCssVarRgb('color', '--destructive');
  const accent = brand !== 'rgba(0, 0, 0, 0)' && brand ? brand : primary;
  const isDark = mode === 'dark';

  const chartColors = (['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5'] as const).map(
    (token) => rgbCss(readCssVarRgb('color', token)),
  );
  GRAPH_THEME.palette.semantic = [
    chartColors[0] ?? rgbCss(primary),
    chartColors[1] ?? rgbCss(ok),
    chartColors[2] ?? rgbCss(warn),
    chartColors[3] ?? rgbCss(signal),
    chartColors[4] ?? rgbCss(primary),
    rgbCss(ok),
    rgbCss(warn),
  ];

  GRAPH_THEME.ui.text.strong = foreground;
  GRAPH_THEME.ui.text.body = foreground;
  GRAPH_THEME.ui.text.muted = mutedForeground;
  GRAPH_THEME.ui.text.subtle = mutedForeground;
  GRAPH_THEME.ui.text.inverse = background;

  GRAPH_THEME.ui.surface.app = background;
  GRAPH_THEME.ui.surface.stage = background;
  GRAPH_THEME.ui.surface.card = card;
  GRAPH_THEME.ui.surface.cardSubtle = card;
  GRAPH_THEME.ui.surface.cardStrong = card;
  GRAPH_THEME.ui.surface.panel = card;
  GRAPH_THEME.ui.surface.panelBorder = rgbaFromRgb(border, isDark ? 0.55 : 0.35);
  GRAPH_THEME.ui.surface.divider = rgbaFromRgb(border, 0.4);
  GRAPH_THEME.ui.surface.shadow = isDark
    ? '0 22px 60px rgba(0, 0, 0, 0.34)'
    : '0 12px 28px -16px rgba(20, 24, 40, 0.09)';

  GRAPH_THEME.ui.scene.background = background;
  GRAPH_THEME.ui.scene.radialGlow = 'none';
  GRAPH_THEME.ui.scene.grid = 'transparent';
  GRAPH_THEME.ui.scene.gridStrong = 'transparent';
  GRAPH_THEME.ui.scene.vignette = 'none';

  GRAPH_THEME.ui.control.defaultBg = rgbaFromRgb(muted, isDark ? 0.45 : 0.65);
  GRAPH_THEME.ui.control.defaultBorder = rgbaFromRgb(border, 0.5);
  GRAPH_THEME.ui.control.defaultText = foreground;
  GRAPH_THEME.ui.control.hoverBg = rgbaFromRgb(muted, isDark ? 0.65 : 0.85);
  GRAPH_THEME.ui.control.activeBg = rgbaFromRgb(accent, isDark ? 0.22 : 0.14);
  GRAPH_THEME.ui.control.activeBorder = rgbaFromRgb(accent, 0.45);
  GRAPH_THEME.ui.control.activeText = foreground;
  GRAPH_THEME.ui.control.primaryBg = rgbaFromRgb(accent, isDark ? 0.28 : 0.16);
  GRAPH_THEME.ui.control.primaryBorder = rgbaFromRgb(accent, 0.4);
  GRAPH_THEME.ui.control.primaryText = foreground;
  GRAPH_THEME.ui.control.inputBg = rgbaFromRgb(muted, isDark ? 0.35 : 0.5);
  GRAPH_THEME.ui.control.inputBorder = rgbaFromRgb(border, 0.45);
  GRAPH_THEME.ui.control.focusRing = rgbaFromRgb(accent, 0.2);
  GRAPH_THEME.ui.control.dangerText = rgbCss(destructive);
  GRAPH_THEME.ui.control.disabledText = rgbaFromRgb(mutedForeground, 0.42);

  GRAPH_THEME.ui.timeline.background = card;
  GRAPH_THEME.ui.timeline.border = rgbaFromRgb(border, isDark ? 0.14 : 0.2);
  GRAPH_THEME.ui.timeline.gridMinor = rgbaFromRgb(border, isDark ? 0.05 : 0.07);
  GRAPH_THEME.ui.timeline.gridMajor = rgbaFromRgb(border, isDark ? 0.1 : 0.14);
  GRAPH_THEME.ui.timeline.text = mutedForeground;
  GRAPH_THEME.ui.timeline.textStrong = foreground;
  GRAPH_THEME.ui.timeline.playhead = accent;
  GRAPH_THEME.ui.timeline.playheadSoft = rgbaFromRgb(accent, isDark ? 0.38 : 0.32);

  GRAPH_THEME.palette.background.canvas = background;
  GRAPH_THEME.palette.background.shell = rgbaFromRgb(card, 0.92);
  GRAPH_THEME.palette.background.shellBorder = rgbaFromRgb(border, 0.4);
  GRAPH_THEME.palette.background.grid = rgbaFromRgb(border, 0.12);
  GRAPH_THEME.palette.background.vignette = 'transparent';
  GRAPH_THEME.palette.background.shellGlow = 'transparent';
  GRAPH_THEME.palette.background.nodeBorder = rgbaFromRgb(border, 0.65);
  GRAPH_THEME.palette.muted.fallback = rgbaFromRgb(mutedForeground, isDark ? 0.18 : 0.22);

  const lightEdgeInk = mixRgbCss(foreground, mutedForeground, 0.65);
  /** Dark canvas: Basis `--muted-foreground` is ~70% L — pull ink toward `--background` so edges stay ambient. */
  const darkCanvasEdgeInk = mixRgbCss(rgbCss(mutedForeground), rgbCss(background), 0.08);
  const darkCanvasEdgeEmphasis = mixRgbCss(rgbCss(mutedForeground), rgbCss(background), 0.14);

  GRAPH_THEME.palette.accent.selected = rgbCss(accent);
  GRAPH_THEME.palette.accent.hovered = rgbCss(primary);
  GRAPH_THEME.palette.accent.path = rgbCss(warn);
  GRAPH_THEME.palette.accent.temporal = rgbCss(info !== 'rgba(0, 0, 0, 0)' && info ? info : signal);
  GRAPH_THEME.palette.accent.provenance = chartColors[3] ?? rgbCss(primary);
  GRAPH_THEME.palette.accent.inferred = rgbCss(destructive);

  GRAPH_THEME.palette.overview.nodeBase = isDark ? rgbaFromRgb(card, 0.95) : rgbaFromRgb(muted, 0.9);
  GRAPH_THEME.palette.overview.nodeCore = mutedForeground;
  GRAPH_THEME.palette.overview.nodeMuted = isDark ? background : muted;
  GRAPH_THEME.palette.overview.nodeBorder = rgbaFromRgb(border, 0.7);
  const edgeStroke = isDark ? darkCanvasEdgeInk : lightEdgeInk;
  const edgeEmphasis = isDark ? darkCanvasEdgeEmphasis : rgbCss(foreground);
  GRAPH_THEME.palette.overview.edgeStructure = edgeStroke;
  GRAPH_THEME.palette.overview.edgeBackbone = edgeEmphasis;
  GRAPH_THEME.palette.overview.edgeInspection = edgeStroke;
  GRAPH_THEME.palette.muted.edgeOverview = edgeStroke;
  GRAPH_THEME.palette.muted.edgeStructure = edgeStroke;
  GRAPH_THEME.palette.muted.edgeInspection = edgeStroke;
  GRAPH_THEME.palette.muted.edgeFocus = rgbCss(accent);

  applyCanvasEdgeVisibility(isDark);

  // Muted nodes during focus/hover are readable on dark canvas at ~0.16 alpha; light backgrounds need more ink.
  GRAPH_THEME.nodes.mutedAlpha = isDark ? 0.16 : 0.44;
  GRAPH_THEME.palette.overview.nodeMutedFillAlpha = isDark ? 0.42 : 0.62;

  GRAPH_THEME.labels.chip.background = rgbaFromRgb(card, isDark ? 0.94 : 0.96);
  GRAPH_THEME.labels.chip.borderColor = rgbaFromRgb(border, isDark ? 0.55 : 0.4);
  GRAPH_THEME.labels.chip.textColor = foreground;
  GRAPH_THEME.labels.chip.shadowColor = isDark ? 'rgba(0, 0, 0, 0.38)' : 'rgba(20, 24, 40, 0.08)';
  GRAPH_THEME.labels.chip.shadowAlpha = isDark ? 0.1 : 0.07;
  GRAPH_THEME.labels.chip.shadowBlur = isDark ? 7 : 5;

  GRAPH_THEME.labels.hoverCard.background = rgbaFromRgb(card, isDark ? 0.96 : 0.98);
  GRAPH_THEME.labels.hoverCard.borderColor = rgbaFromRgb(border, isDark ? 0.5 : 0.38);
  GRAPH_THEME.labels.hoverCard.textColor = foreground;
  GRAPH_THEME.labels.hoverCard.metaColor = mutedForeground;
  GRAPH_THEME.labels.hoverCard.shadowColor = isDark ? 'rgba(0, 0, 0, 0.32)' : 'rgba(20, 24, 40, 0.06)';
  GRAPH_THEME.labels.hoverCard.shadowAlpha = isDark ? 0.08 : 0.06;
  GRAPH_THEME.labels.hoverCard.shadowBlur = 6;

  const fontFamily = getComputedStyle(document.documentElement).fontFamily;
  if (fontFamily) {
    GRAPH_THEME.labels.chip.fontFamily = fontFamily;
    GRAPH_THEME.labels.hoverCard.fontFamily = fontFamily;
  }

  GRAPH_THEME.nodes.selectedRing.color = rgbCss(accent);
  GRAPH_THEME.nodes.badges.inferred.color = rgbCss(warn);
  GRAPH_THEME.nodes.badges.temporal.color = rgbCss(info !== 'rgba(0, 0, 0, 0)' && info ? info : signal);
  GRAPH_THEME.nodes.badges.provenance.color = chartColors[2] ?? rgbCss(primary);
  GRAPH_THEME.nodes.badge.textColor = rgbCss(background);
  GRAPH_THEME.nodes.badge.background = rgbaFromRgb(card, isDark ? 0.84 : 0.92);
  GRAPH_THEME.nodes.badge.stroke = rgbaFromRgb(border, 0.55);
}

/** Sigma label colors — decouple edge text from faint edge stroke colors. */
export function getSigmaCanvasLabelSettings() {
  return {
    labelColor: { color: GRAPH_THEME.ui.text.body },
    edgeLabelColor: {
      attribute: 'labelColor',
      color: GRAPH_THEME.ui.text.muted,
    },
  };
}
