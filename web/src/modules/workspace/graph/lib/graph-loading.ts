import {
  type GraphScreenLocale,
  graphLoadPhaseTitle,
  graphLoadStageLabel as graphLoadStageLabelForLocale,
} from '../i18n/screen-copy.js';
import type { GraphLoadPhase, GraphLoadProgress, GraphLoadProgressKind, GraphLayoutSource, GraphLayoutState } from "./types";

export const GRAPH_LOAD_STAGE_SEQUENCE: Exclude<GraphLoadPhase, "ready">[] = [
  "bootstrapping",
  "fetching_nodes",
  "fetching_edges",
  "computing_styling",
  "hydrating_scene",
  "stabilizing_layout",
];

export function getGraphLoadTitle(
  phase: GraphLoadPhase,
  locale: GraphScreenLocale = "en",
): string {
  return graphLoadPhaseTitle(locale, phase);
}

export function getGraphLoadStageLabel(
  phase: Exclude<GraphLoadPhase, "ready">,
  locale: GraphScreenLocale = "en",
): string {
  return graphLoadStageLabelForLocale(locale, phase);
}

export function createGraphLoadProgress(input: {
  phase: GraphLoadPhase;
  message: string;
  progressKind: GraphLoadProgressKind;
  locale?: GraphScreenLocale;
  loaded?: number | null;
  total?: number | null;
  nodesLoaded?: number;
  nodesTotal?: number | null;
  edgesLoaded?: number;
  edgesTotal?: number | null;
  showGraphBehind?: boolean;
  layoutSource?: GraphLayoutSource;
  layoutState?: GraphLayoutState;
}): GraphLoadProgress {
  const phaseIndex = GRAPH_LOAD_STAGE_SEQUENCE.indexOf(input.phase as Exclude<GraphLoadPhase, "ready">);

  return {
    phase: input.phase,
    title: getGraphLoadTitle(input.phase, input.locale ?? "en"),
    message: input.message,
    progressKind: input.progressKind,
    loaded: input.loaded ?? null,
    total: input.total ?? null,
    nodesLoaded: input.nodesLoaded ?? 0,
    nodesTotal: input.nodesTotal ?? null,
    edgesLoaded: input.edgesLoaded ?? 0,
    edgesTotal: input.edgesTotal ?? null,
    showGraphBehind: input.showGraphBehind ?? false,
    stageIndex: phaseIndex >= 0 ? phaseIndex + 1 : GRAPH_LOAD_STAGE_SEQUENCE.length,
    stageCount: GRAPH_LOAD_STAGE_SEQUENCE.length,
    layoutSource: input.layoutSource,
    layoutState: input.layoutState,
  };
}
