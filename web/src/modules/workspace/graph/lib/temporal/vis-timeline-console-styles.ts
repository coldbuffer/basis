/** Shared vis-timeline skin for workspace console surfaces (light/dark via CSS variables). */
export function buildVisTimelineConsoleStyles(config: {
  wrapClass: string;
  markers: Array<{ id: string; line: string; marker: string }>;
}): string {
  const markerRules = config.markers
    .map(
      (marker) => `
  .${config.wrapClass} .vis-custom-time.${marker.id} {
    background: ${marker.line} !important;
    width: 2px !important;
    cursor: ew-resize !important;
    z-index: 5 !important;
  }
  .${config.wrapClass} .vis-custom-time.${marker.id} > .vis-custom-time-marker {
    background: ${marker.marker} !important;
    color: var(--primary-foreground) !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    border-radius: 4px !important;
    padding: 1px 5px !important;
    white-space: nowrap !important;
  }`,
    )
    .join('\n');

  return `
  .${config.wrapClass} .vis-timeline { border: none !important; background: transparent !important; overflow: visible !important; }
  .${config.wrapClass} .vis-panel.vis-background, .${config.wrapClass} .vis-panel.vis-center { background: transparent !important; }
  .${config.wrapClass} .vis-panel { border-color: color-mix(in oklch, var(--border) 80%, transparent) !important; }
  .${config.wrapClass} .vis-time-axis .vis-text {
    color: var(--muted-foreground) !important;
    font-size: 11px !important;
    font-family: var(--font-mono) !important;
    padding-top: 3px !important;
  }
  .${config.wrapClass} .vis-time-axis .vis-text.vis-major {
    color: var(--foreground) !important;
    font-weight: 600 !important;
    font-size: 11px !important;
  }
  .${config.wrapClass} .vis-time-axis .vis-grid.vis-minor { border-color: color-mix(in oklch, var(--border) 40%, transparent) !important; }
  .${config.wrapClass} .vis-time-axis .vis-grid.vis-major { border-color: color-mix(in oklch, var(--border) 70%, transparent) !important; }
  .${config.wrapClass} .vis-current-time { display: none !important; }
  .${config.wrapClass} .vis-panel.vis-left { display: none !important; }
  ${markerRules}
`;
}
