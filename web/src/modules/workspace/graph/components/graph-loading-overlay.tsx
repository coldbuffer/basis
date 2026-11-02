import { Button } from "@/components/ui/button.js";
import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useEffect, useRef, useState } from "react";

import {
  graphLoaderMetric,
  graphLoaderMetricAccent,
  graphProgressWidthStyle,
} from "@/lib/ui-classes/graph-ui.js";
import { fmt, formatLocaleNumber } from "@/i18n/format.js";

import {
  graphCopy,
  graphLoadOverlayCopy,
  graphLoadPhaseTitle,
  type GraphScreenLocale,
} from '../i18n/screen-copy.js';
import { GRAPH_LOAD_STAGE_SEQUENCE, createGraphLoadProgress, getGraphLoadStageLabel } from '../lib/graph-loading.js';
import type { GraphLoadProgress } from '../lib/types.js';

const LOADING_OVERLAY_CSS = `
  .graph-stage-loader {
    position: absolute;
    inset: 0;
    z-index: 9;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    opacity: 1;
    transition: opacity 220ms ease, transform 220ms ease;
  }
  .graph-stage-loader[data-exiting="true"] {
    opacity: 0;
    transform: scale(0.985);
  }
  .graph-stage-loader[data-bg="solid"] {
    background: color-mix(in oklch, var(--background) 52%, transparent);
  }
  .graph-stage-loader[data-bg="live"] {
    background: color-mix(in oklch, var(--background) 16%, transparent);
  }
  .graph-stage-loader-card {
    width: min(540px, calc(100% - 48px));
    border-radius: calc(var(--radius) + 6px);
    padding: 20px 20px 18px;
    border: 1px solid var(--border);
    background: color-mix(in oklch, var(--card) 96%, transparent);
    color: var(--foreground);
    box-shadow: var(--shadow);
    backdrop-filter: blur(18px) saturate(1.08);
    -webkit-backdrop-filter: blur(18px) saturate(1.08);
  }
  .graph-stage-loader-card[data-live="true"] {
    width: min(500px, calc(100% - 56px));
    background: color-mix(in oklch, var(--card) 92%, transparent);
    box-shadow: var(--shadow);
  }
  .graph-stage-loader-beacon {
    position: relative;
    width: 12px;
    height: 12px;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--primary), var(--warn));
    box-shadow: 0 0 18px color-mix(in oklch, var(--primary) 35%, transparent);
  }
  .graph-stage-loader-beacon::after {
    content: "";
    position: absolute;
    inset: -7px;
    border-radius: inherit;
    border: 1px solid color-mix(in oklch, var(--primary) 22%, var(--border));
    animation: graph-loader-beacon 1.9s ease-out infinite;
  }
  .graph-stage-loader-track {
    display: grid;
    grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 8px;
  }
  .graph-stage-loader-step {
    border-radius: 999px;
    padding: 7px 0;
    text-align: center;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border: 1px solid var(--border);
    color: var(--muted-foreground);
    background: var(--muted);
  }
  .graph-stage-loader-step[data-state="done"] {
    color: var(--foreground);
    border-color: var(--border);
    background: color-mix(in oklch, var(--brand-primary) 8%, var(--muted));
  }
  .graph-stage-loader-step[data-state="active"] {
    color: var(--foreground);
    border-color: color-mix(in oklch, var(--brand-primary) 42%, var(--border));
    background: color-mix(in oklch, var(--brand-primary) 12%, var(--card));
  }
  .graph-stage-loader-bar {
    position: relative;
    width: 100%;
    height: 12px;
    overflow: hidden;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--muted);
  }
  .graph-stage-loader-bar-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--primary), var(--warn));
    box-shadow: 0 0 30px color-mix(in oklch, var(--primary) 28%, transparent);
    transition: width 220ms ease;
  }
  .graph-stage-loader-bar-indeterminate::before {
    content: "";
    position: absolute;
    top: 1px;
    bottom: 1px;
    width: 34%;
    border-radius: 999px;
    background: linear-gradient(90deg, transparent, var(--primary), var(--warn), transparent);
    box-shadow: 0 0 26px color-mix(in oklch, var(--primary) 18%, transparent);
    animation: graph-loader-sweep 1.5s cubic-bezier(0.22, 1, 0.36, 1) infinite;
  }
  @keyframes graph-loader-beacon {
    0% { transform: scale(0.72); opacity: 0.6; }
    100% { transform: scale(1.44); opacity: 0; }
  }
  @keyframes graph-loader-sweep {
    0% { transform: translateX(-120%); }
    100% { transform: translateX(360%); }
  }
  .graph-stage-loader-card[data-error="true"] {
    pointer-events: auto;
    border-color: color-mix(in oklch, var(--destructive) 40%, var(--border));
    background: color-mix(in oklch, var(--destructive) 5%, var(--card));
  }
  .graph-stage-loader-error-mark {
    width: 38px;
    height: 38px;
    flex: 0 0 auto;
    border-radius: 12px;
    display: grid;
    place-items: center;
    color: #ff9e97;
    background: rgba(255, 123, 114, 0.12);
    border: 1px solid rgba(255, 123, 114, 0.28);
  }
  .graph-stage-loader-error-detail {
    padding: 10px 12px;
    border-radius: 10px;
    background: var(--muted);
    border: 1px solid color-mix(in oklch, var(--destructive) 24%, var(--border));
    color: var(--destructive);
    font-family: "JetBrains Mono", "Fira Code", Consolas, monospace;
    font-size: 12px;
    line-height: 1.55;
    word-break: break-word;
  }
  .graph-stage-loader-retry {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 9px 16px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--primary);
    color: var(--primary-foreground);
    transition: 160ms ease;
  }
  .graph-stage-loader-retry:hover {
    opacity: 0.9;
  }
  .graph-stage-loader-retry:focus-visible {
    outline: 2px solid #7fd0ff;
    outline-offset: 2px;
  }
`;

function formatLayoutSource(
  locale: GraphScreenLocale,
  source: GraphLoadProgress["layoutSource"],
) {
  const o = graphLoadOverlayCopy(locale);
  switch (source) {
    case "provided":
      return o.layout_provided;
    case "carried":
      return o.layout_carried;
    case "runtime":
      return o.layout_runtime;
    default:
      return null;
  }
}

function formatLayoutState(
  locale: GraphScreenLocale,
  state: GraphLoadProgress["layoutState"],
) {
  const o = graphLoadOverlayCopy(locale);
  switch (state) {
    case "bootstrapping":
      return o.state_bootstrapping;
    case "running":
      return o.state_running;
    case "interactive":
      return o.state_interactive;
    case "stabilized":
      return o.state_stabilized;
    case "failed":
      return o.state_failed;
    default:
      return null;
  }
}

export function GraphLoadingOverlay({
  locale = "en",
  progress,
  visible,
  showGraphBehind,
  error = null,
  onRetry,
}: {
  locale?: GraphScreenLocale;
  progress: GraphLoadProgress | null;
  visible: boolean;
  showGraphBehind: boolean;
  error?: string | null;
  onRetry?: () => void;
}) {
  const [renderVisible, setRenderVisible] = useState(visible);
  const [exiting, setExiting] = useState(false);
  const [displayProgress, setDisplayProgress] = useState<GraphLoadProgress>(
    progress ?? createGraphLoadProgress({
      phase: "bootstrapping",
      message: graphLoadPhaseTitle(locale, "bootstrapping"),
      progressKind: "indeterminate",
      locale,
    }),
  );
  const exitTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (progress) {
      setDisplayProgress(progress);
    }
  }, [progress]);

  useEffect(() => {
    if (visible) {
      if (exitTimerRef.current !== null) {
        window.clearTimeout(exitTimerRef.current);
        exitTimerRef.current = null;
      }
      setRenderVisible(true);
      setExiting(false);
      return;
    }

    if (!renderVisible) {
      return;
    }

    setExiting(true);
    exitTimerRef.current = window.setTimeout(() => {
      setRenderVisible(false);
      setExiting(false);
      exitTimerRef.current = null;
    }, 220);

    return () => {
      if (exitTimerRef.current !== null) {
        window.clearTimeout(exitTimerRef.current);
        exitTimerRef.current = null;
      }
    };
  }, [renderVisible, visible]);

  if (!renderVisible) {
    return null;
  }

  if (error) {
    return (
      <div className="graph-stage-loader" data-exiting={exiting} data-bg="solid">
        <style>{LOADING_OVERLAY_CSS}</style>
        <div className="graph-stage-loader-card" data-error="true" role="alert">
          <div className="mb-3.5 flex items-start gap-3.5">
            <div className="graph-stage-loader-error-mark" aria-hidden="true">
              <PublicIcon name="alert-triangle" size={18} />
            </div>
            <div className="min-w-0">
              <div className="mb-1.5 text-xl font-bold tracking-tight text-foreground">
                {graphCopy(locale, "loadErrorTitle")}
              </div>
              <div className="text-[13px] leading-normal text-muted-foreground">
                {graphCopy(locale, "loadErrorBody")}
              </div>
            </div>
          </div>

          <div className="graph-stage-loader-error-detail">{error}</div>

          {onRetry ? (
            <div className="mt-4 flex gap-2.5">
              <Button type="button" className="graph-stage-loader-retry" onClick={onRetry}>
                <PublicIcon name="arrow-refresh-01" size={14} />
                {graphCopy(locale, "loadRetry")}
              </Button>
            </div>
          ) : null}
        </div>
      </div>
    );
  }

  const activeProgress = progress ?? displayProgress;
  const isLiveStage = activeProgress.phase === "stabilizing_layout" || activeProgress.showGraphBehind || showGraphBehind;
  const determinateRatio = activeProgress.progressKind === "determinate" && activeProgress.total
    ? Math.max(0.05, Math.min(activeProgress.loaded ?? 0, activeProgress.total) / Math.max(activeProgress.total, 1))
    : null;
  const overlay = graphLoadOverlayCopy(locale);
  const layoutSource = formatLayoutSource(locale, activeProgress.layoutSource);
  const layoutState = formatLayoutState(locale, activeProgress.layoutState);

  return (
    <div
      className="graph-stage-loader"
      data-exiting={exiting}
      data-bg={isLiveStage ? "live" : "solid"}
    >
      <style>{LOADING_OVERLAY_CSS}</style>
      <div className="graph-stage-loader-card" data-live={isLiveStage}>
        <div className="mb-3.5 flex items-start justify-between gap-3.5">
          <div className="min-w-0">
            <div className="mb-1.5 text-xl font-bold tracking-tight text-foreground">
              {activeProgress.title}
            </div>
            <div className="text-[13px] leading-normal text-muted-foreground">
              {activeProgress.message}
            </div>
          </div>
          <div className="inline-flex shrink-0 items-center gap-2.5">
            <div className="graph-stage-loader-beacon" aria-hidden="true" />
            <div className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
              {fmt(overlay.stage_badge, {
                current: activeProgress.stageIndex ?? 1,
                total: activeProgress.stageCount ?? GRAPH_LOAD_STAGE_SEQUENCE.length,
              })}
            </div>
          </div>
        </div>

        <div className="graph-stage-loader-track mb-3.5">
          {GRAPH_LOAD_STAGE_SEQUENCE.map((phase, index) => {
            const current = activeProgress.stageIndex ?? 1;
            const state = index + 1 < current ? "done" : index + 1 === current ? "active" : "upcoming";
            return (
              <div key={phase} className="graph-stage-loader-step" data-state={state}>
                {getGraphLoadStageLabel(phase, locale)}
              </div>
            );
          })}
        </div>

        <div className="mb-2 flex items-baseline justify-between gap-3">
          <div className="text-xs font-semibold text-foreground">
            {activeProgress.progressKind === "determinate" && activeProgress.total
              ? fmt(overlay.stage_counts, {
                  loaded: formatLocaleNumber(locale, activeProgress.loaded ?? 0),
                  total: formatLocaleNumber(locale, activeProgress.total),
                })
              : overlay.stage_working}
          </div>
          <div className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
            {activeProgress.progressKind === "determinate" && determinateRatio !== null
              ? `${Math.round(determinateRatio * 100)}%`
              : overlay.live}
          </div>
        </div>

        <div className={`graph-stage-loader-bar ${activeProgress.progressKind === "indeterminate" ? "graph-stage-loader-bar-indeterminate" : ""}`}>
          {activeProgress.progressKind === "determinate" && determinateRatio !== null ? (
            <span className="graph-stage-loader-bar-fill" style={graphProgressWidthStyle(determinateRatio)} />
          ) : null}
        </div>

        <div className="mt-3.5 flex flex-wrap gap-2.5">
          <span className={graphLoaderMetric}>
            {activeProgress.nodesTotal
              ? fmt(overlay.nodes_with_total, {
                  loaded: formatLocaleNumber(locale, activeProgress.nodesLoaded),
                  total: formatLocaleNumber(locale, activeProgress.nodesTotal),
                })
              : fmt(overlay.nodes_only, { loaded: formatLocaleNumber(locale, activeProgress.nodesLoaded) })}
          </span>
          <span className={graphLoaderMetric}>
            {activeProgress.edgesTotal
              ? fmt(overlay.edges_with_total, {
                  loaded: formatLocaleNumber(locale, activeProgress.edgesLoaded),
                  total: formatLocaleNumber(locale, activeProgress.edgesTotal),
                })
              : fmt(overlay.edges_only, { loaded: formatLocaleNumber(locale, activeProgress.edgesLoaded) })}
          </span>
          {layoutSource ? (
            <span className={graphLoaderMetricAccent}>
              {layoutSource}
              {layoutState ? ` · ${layoutState}` : ""}
            </span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
