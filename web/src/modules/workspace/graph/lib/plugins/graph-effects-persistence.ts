import type { GraphEffectToggle, GraphEffectsState } from "../types.js";

const STORAGE_PREFIX = "sema.graphEffects.v1:";

export const DEFAULT_GRAPH_EFFECTS_STATE: GraphEffectsState = {
  pathPulseEnabled: false,
  pathFlowEnabled: false,
  lensEnabled: false,
  temporalEmphasisEnabled: false,
  semanticRegionsEnabled: false,
  contoursEnabled: false,
  pathfindingEnabled: false,
  communitiesEnabled: false,
  centralityEnabled: false,
  legendEnabled: false,
  edgeLabelsEnabled: true,
  autoLayoutEnabled: true,
  diagnosticsEnabled: false,
  lensMode: "neighborhood",
  effectQuality: "bounded",
};

const EFFECT_BOOLEAN_KEYS: GraphEffectToggle[] = [
  "pathPulseEnabled",
  "pathFlowEnabled",
  "lensEnabled",
  "temporalEmphasisEnabled",
  "semanticRegionsEnabled",
  "contoursEnabled",
  "pathfindingEnabled",
  "communitiesEnabled",
  "centralityEnabled",
  "legendEnabled",
  "edgeLabelsEnabled",
  "autoLayoutEnabled",
  "diagnosticsEnabled",
];

export function sanitizeGraphEffectsState(
  partial: Partial<GraphEffectsState> | null | undefined,
  options: { diagnosticsAllowed: boolean },
): GraphEffectsState {
  const next: GraphEffectsState = { ...DEFAULT_GRAPH_EFFECTS_STATE };
  if (partial) {
    for (const key of EFFECT_BOOLEAN_KEYS) {
      if (typeof partial[key] === "boolean") {
        next[key] = partial[key];
      }
    }
  }
  if (!options.diagnosticsAllowed) {
    next.diagnosticsEnabled = false;
  }
  return next;
}

export function loadGraphEffectsState(
  workspaceId: string,
  options: { diagnosticsAllowed: boolean },
): GraphEffectsState {
  try {
    const raw = localStorage.getItem(`${STORAGE_PREFIX}${workspaceId}`);
    if (!raw) {
      return sanitizeGraphEffectsState(null, options);
    }
    const parsed = JSON.parse(raw) as Partial<GraphEffectsState>;
    return sanitizeGraphEffectsState(parsed, options);
  } catch {
    return sanitizeGraphEffectsState(null, options);
  }
}

export function saveGraphEffectsState(workspaceId: string, state: GraphEffectsState): void {
  const payload: Pick<GraphEffectsState, GraphEffectToggle> = {} as Pick<
    GraphEffectsState,
    GraphEffectToggle
  >;
  for (const key of EFFECT_BOOLEAN_KEYS) {
    payload[key] = state[key];
  }
  try {
    localStorage.setItem(`${STORAGE_PREFIX}${workspaceId}`, JSON.stringify(payload));
  } catch {
    // ignore quota / private mode
  }
}
