import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge.js";
import { Button } from "@/components/ui/button.js";
import { Input } from "@/components/ui/input.js";
import { Separator } from "@/components/ui/separator.js";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleFixedDecimals, formatLocalePercent } from "@/i18n/format.js";
import { workspacePath } from "@/lib/nav/nav-config.js";
import { useWorkspaceCapabilitiesOptional } from "@/lib/workspace/capabilities.js";
import type { GraphScreenLocale } from '../i18n/screen-copy.js';
import { graphNodeTypeLabel } from '../i18n/screen-copy.js';
import {
  inspectorAltPathsBadge,
  inspectorBadgeCount,
  inspectorCanonicalNodeLine,
  inspectorCopy,
  inspectorFocusTitle,
  inspectorHopsSummary,
  inspectorPathBandBadge,
} from '../i18n/graph-inspector-copy.js';
import {
  resolveGraphNodeEvidenceLinks,
  type GraphEvidenceLink,
} from "@/modules/graph/lib/graph-evidence-links.js";
import { GraphInspectorDecisions } from "./graph-inspector-decisions";
import {
  graphNodeAccentDotStyle,
  graphProgressWidthStyle,
  metricBarToneClass,
  metricToneClass,
  pathDistanceBandBadgeClass,
} from "@/lib/ui-classes/graph-ui.js";
import {
  graphInspectorKv,
  graphInspectorKvKey,
  graphInspectorKvValue,
  graphInspectorMetric,
  graphInspectorPanel,
  graphInspectorPathChip,
  graphNodePanelBody,
  graphNodePanelCollapse,
  graphNodePanelSummary,
} from "@/lib/ui-classes/graph-inspector-ui.js";
import { cn } from "@/lib/utils.js";
import { graph } from '@/lib/workspace/graphStore';
import type { FocusedUnavailableReason, GraphSelectedNodeKind } from '../lib/types.js';
import { focusedUnavailableReasonText } from '../i18n/graph-view-copy.js';
import { MarkdownContentViewer } from "./markdown-content-viewer";
import type { MarkdownApplyResult } from '../lib/markdown-resource-client.js';

export type LinkPrediction = {
  target: string;
  type: string;
  label?: string;
  score: number;
};

export type PathResponse = {
  path: string[];
  edge_ids?: string[];
  total_weight: number;
  hop_count: number;
  distance_band: "direct" | "near" | "mid-range" | "distant";
  // FR-1 distance intelligence enrichment
  semantic_similarity?: number | null;
  path_coherence_score?: number | null;
  confidence_decay?: number | null;
  bottleneck_node?: string | null;
  alternative_path_count?: number;
  interpretation?: string;
};

export interface GraphInspectorPanelProps {
  locale?: GraphScreenLocale;
  workspaceId: string;
  graphWriteEnabled?: boolean;
  decisionsEnabled?: boolean;
  nodeId: string;
  inspectableNodeId?: string | null;
  selectedNodeKind?: GraphSelectedNodeKind;
  canActivateFocused?: boolean;
  focusedUnavailableReason?: FocusedUnavailableReason | null;
  predictions: LinkPrediction[];
  predictionType: string;
  onPredictionTypeChange: (value: string) => void;
  onRunPredictions: () => void;
  isRunningPredictions?: boolean;
  pathTargetId: string;
  onPathTargetChange: (value: string) => void;
  onTracePath: () => void;
  pathResult: PathResponse | null;
  onDownloadProvenance: (format: "json" | "markdown") => void;
  onFocusNode?: (nodeId: string) => void;
  onMarkdownApplied?: (result: MarkdownApplyResult) => void;
  onMarkdownDirtyChange?: (dirty: boolean) => void;
  onArchiveNode?: (nodeId: string) => void | Promise<void>;
  isArchivingNode?: boolean;
}

const PROVENANCE_KEYS = ["source", "source_url", "pmid", "pmids", "evidence", "provenance", "confidence"] as const;

const inspectorSectionClass =
  "flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3.5 shadow-sm";
const inspectorSectionTitleClass =
  "text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground";
const inspectorEmptyClass = "text-xs leading-relaxed text-muted-foreground";
const inspectorNoticeClass =
  "mt-3 rounded-lg border border-border bg-muted/40 px-3 py-2.5 text-sm leading-relaxed text-foreground";

function sourceAttribution(properties: Record<string, unknown>) {
  return PROVENANCE_KEYS
    .filter((key) => key in properties)
    .map((key) => ({ key, value: properties[key] }));
}

/* ─── Path Distance Intelligence Panel ──────────────────────────── */

function PathDistanceIntelPanel({
  locale,
  result,
}: {
  locale: GraphScreenLocale;
  result: PathResponse;
}) {
  const hasMetrics =
    result.confidence_decay != null ||
    result.semantic_similarity != null ||
    result.path_coherence_score != null ||
    result.bottleneck_node != null;

  return (
    <div className="mt-2 flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className={pathDistanceBandBadgeClass(result.distance_band)}>
          {inspectorPathBandBadge(locale, result.distance_band, result.hop_count)}
        </Badge>
        {(result.alternative_path_count ?? 0) > 0 ? (
          <Badge variant="secondary">
            {inspectorAltPathsBadge(locale, result.alternative_path_count ?? 0)}
          </Badge>
        ) : null}
      </div>

      {hasMetrics ? (
        <div className="grid grid-cols-2 gap-2">
          {result.confidence_decay != null ? (
            <div className={graphInspectorMetric}>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {inspectorCopy(locale, "confidenceDecay")}
              </div>
              <div
                className={cn(
                  "text-sm font-semibold tabular-nums",
                  metricToneClass(result.confidence_decay),
                )}
              >
                {formatLocalePercent(locale, result.confidence_decay, 1)}
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full rounded-full transition-[width] duration-300",
                    metricBarToneClass(result.confidence_decay),
                  )}
                  style={graphProgressWidthStyle(result.confidence_decay)}
                />
              </div>
            </div>
          ) : null}
          {result.semantic_similarity != null ? (
            <div className={graphInspectorMetric}>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {inspectorCopy(locale, "semanticSim")}
              </div>
              <div className="text-sm font-semibold tabular-nums text-sky-600 dark:text-sky-400">
                {formatLocalePercent(locale, result.semantic_similarity, 1)}
              </div>
              <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-sky-500 transition-[width] duration-300"
                  style={graphProgressWidthStyle(result.semantic_similarity)}
                />
              </div>
            </div>
          ) : null}
          {result.path_coherence_score != null ? (
            <div className={graphInspectorMetric}>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {inspectorCopy(locale, "pathCoherence")}
              </div>
              <div className="text-sm font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">
                {formatLocalePercent(locale, result.path_coherence_score, 1)}
              </div>
            </div>
          ) : null}
          {result.bottleneck_node ? (
            <div className={graphInspectorMetric}>
              <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                {inspectorCopy(locale, "bottleneck")}
              </div>
              <div className="truncate text-xs font-semibold text-amber-600 dark:text-amber-400" title={result.bottleneck_node}>
                {getNodeLabel(result.bottleneck_node)}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {result.interpretation ? (
        <p className="rounded-lg border border-border bg-muted/35 px-2.5 py-2 text-xs leading-relaxed text-muted-foreground">
          {result.interpretation}
        </p>
      ) : null}
    </div>
  );
}

/* ─── Path Flow Visualizer ──────────────────────────────────────── */

function getNodeLabel(nodeId: string): string {
  if (!graph.hasNode(nodeId)) return nodeId;
  const attrs = graph.getNodeAttributes(nodeId) as { label?: string; content?: string };
  return String(attrs.label ?? attrs.content ?? nodeId);
}

function getEdgeLabelBetween(sourceId: string, targetId: string, edgeIds?: string[]): string {
  // Try to find the specific edge from edgeIds first
  if (edgeIds) {
    for (const edgeId of edgeIds) {
      if (graph.hasEdge(edgeId)) {
        const [src, tgt] = graph.extremities(edgeId);
        if ((src === sourceId && tgt === targetId) || (src === targetId && tgt === sourceId)) {
          const attrs = graph.getEdgeAttributes(edgeId) as { edgeType?: string };
          return attrs.edgeType ?? "→";
        }
      }
    }
  }
  // Fallback: find any edge between the pair
  if (graph.hasNode(sourceId) && graph.hasNode(targetId)) {
    let label = "→";
    graph.forEachEdge(sourceId, targetId, (_edgeId, attrs) => {
      const edgeAttrs = attrs as { edgeType?: string };
      if (edgeAttrs.edgeType) label = edgeAttrs.edgeType;
    });
    return label;
  }
  return "→";
}

function PathFlowViz({
  locale,
  path,
  edgeIds,
  totalWeight,
  bottleneckNodeId,
  onFocusNode,
}: {
  locale: GraphScreenLocale;
  path: string[];
  edgeIds?: string[];
  totalWeight: number;
  bottleneckNodeId?: string | null;
  onFocusNode?: (nodeId: string) => void;
}) {
  if (path.length === 0) {
    return <p className={inspectorEmptyClass}>{inspectorCopy(locale, "noPathFound")}</p>;
  }

  return (
    <div>
      <div className="flex flex-wrap items-center gap-y-2">
        {path.map((nodeId, index) => {
          const label = getNodeLabel(nodeId);
          const edgeLabel =
            index < path.length - 1
              ? getEdgeLabelBetween(nodeId, path[index + 1], edgeIds)
              : null;

          return (
            <div key={`${nodeId}-${index}`} className="contents">
              <Button
                type="button"
                variant="ghost"
                onClick={() => onFocusNode?.(nodeId)}
                title={inspectorFocusTitle(locale, nodeId, nodeId === bottleneckNodeId)}
                data-bottleneck={nodeId === bottleneckNodeId ? "true" : undefined}
                className={cn(
                  cn(graphInspectorPathChip, "h-auto font-normal"),
                  onFocusNode ? "cursor-pointer" : "cursor-default",
                )}
              >
                <span className="inline-flex size-4 shrink-0 items-center justify-center rounded-full bg-muted text-[9px] font-bold text-muted-foreground">
                  {index + 1}
                </span>
                <span className="truncate">{label}</span>
              </Button>

              {edgeLabel !== null ? (
                <div className="inline-flex shrink-0 items-center gap-0.5 px-0.5">
                  <div className="h-px w-3 bg-border" />
                  <span className="max-w-[4.5rem] truncate text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {edgeLabel}
                  </span>
                  <div className="flex items-center">
                    <div className="h-px w-2 bg-border" />
                    <div className="size-0 border-y-[3px] border-l-[4px] border-y-transparent border-l-muted-foreground/50" />
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span>{inspectorCopy(locale, "totalWeight")}</span>
        <span className="font-semibold tabular-nums text-foreground">
          {formatLocaleFixedDecimals(locale, totalWeight, 3)}
        </span>
        <span aria-hidden>·</span>
        <span>{inspectorHopsSummary(locale, path.length)}</span>
      </div>
    </div>
  );
}

/* ─── Main Panel ─────────────────────────────────────────────────── */

export function GraphInspectorPanel({
  locale: localeProp,
  workspaceId,
  nodeId,
  inspectableNodeId,
  selectedNodeKind = "none",
  canActivateFocused = false,
  focusedUnavailableReason = null,
  predictions,
  predictionType,
  onPredictionTypeChange,
  onRunPredictions,
  isRunningPredictions = false,
  pathTargetId,
  onPathTargetChange,
  onTracePath,
  pathResult,
  onDownloadProvenance,
  onFocusNode,
  onMarkdownApplied,
  onMarkdownDirtyChange,
  onArchiveNode,
  isArchivingNode = false,
  graphWriteEnabled = true,
  decisionsEnabled = false,
}: GraphInspectorPanelProps) {
  const { locale: i18nLocale } = useI18n();
  const loc: GraphScreenLocale =
    localeProp ?? i18nLocale;
  const provenanceEnabled = useWorkspaceCapabilitiesOptional()?.caps?.provenance === true;

  if (!nodeId) {
    return (
      <div className={cn(
        graphInspectorPanel,
        "flex min-h-[240px] flex-col items-center justify-center gap-3 px-6 py-10 text-center",
      )}>
        <div className="flex size-10 items-center justify-center rounded-full border border-border bg-muted/50">
          <div className="size-3.5 rounded-full bg-primary/30" />
        </div>
        <p className="max-w-[28ch] text-sm leading-relaxed text-muted-foreground">
          {inspectorCopy(loc, "emptyHint")}
        </p>
      </div>
    );
  }

  const resolvedNodeId = inspectableNodeId && graph.hasNode(inspectableNodeId) ? inspectableNodeId : null;
  const directlyInspectable = graph.hasNode(nodeId);
  const effectiveNodeId = directlyInspectable ? nodeId : resolvedNodeId;
  const actionNodeId = directlyInspectable ? nodeId : resolvedNodeId;
  const groupedDisplaySelection = selectedNodeKind === "grouped" && !directlyInspectable;

  if (!effectiveNodeId) {
    return (
      <aside className={cn(graphInspectorPanel, "flex flex-col gap-4 p-4 pb-8 md:p-5")}>
        <header className="space-y-2 border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <span className="size-2 shrink-0 rounded-full bg-primary" />
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {inspectorCopy(loc, "selection")}
            </span>
          </div>
          <h2 className="line-clamp-2 text-lg font-semibold leading-snug break-words" title={nodeId}>
            {nodeId}
          </h2>
          <p className="font-mono text-xs break-all text-muted-foreground">{nodeId}</p>
        </header>
        <div className={inspectorNoticeClass}>
          <p className="mb-1.5 font-medium text-foreground">
            {inspectorCopy(loc, "notInspectableTitle")}
          </p>
          <p className="text-muted-foreground">
            {canActivateFocused
              ? inspectorCopy(loc, "useFocusHint")
              : focusedUnavailableReasonText(focusedUnavailableReason, loc)}
          </p>
        </div>
      </aside>
    );
  }

  const attributes = graph.getNodeAttributes(effectiveNodeId) as {
    color?: string;
    content?: string;
    label?: string;
    nodeType?: string;
    valid_from?: string | null;
    valid_until?: string | null;
    properties?: Record<string, unknown>;
  };
  const properties = attributes?.properties ?? {};
  const isArchived =
    String(properties.status ?? "").toLowerCase() === "archived"
    || String((attributes as { status?: string }).status ?? "").toLowerCase() === "archived";
  const attribution = sourceAttribution(properties);
  const accentColor = attributes?.color || "#58a6ff";
  const propertyEntries = Object.entries(properties).filter(
    ([key]) =>
      !["x","y","valid_from","valid_until","content","source","source_url","pmid","pmids","evidence","provenance","confidence"].includes(key),
  );
  const nodeContent = (typeof attributes?.content === "string" && attributes.content)
    ? attributes.content
    : (typeof properties.content === "string" && properties.content)
    ? properties.content
    : "";

  const evidenceLinks = workspaceId
    ? resolveGraphNodeEvidenceLinks(
        workspaceId,
        effectiveNodeId,
        attributes?.nodeType,
        properties,
      )
    : [];

  const evidenceLinkLabel = (kind: GraphEvidenceLink["kind"]) => {
    switch (kind) {
      case "sources-doc":
        return inspectorCopy(loc, "evidenceSourcesDoc");
      case "sources-chunk":
        return inspectorCopy(loc, "evidenceSourcesChunk");
      case "search":
        return inspectorCopy(loc, "evidenceSearch");
    }
  };

  return (
    <aside className={cn(graphInspectorPanel, "flex flex-col gap-4 p-4 pb-8 md:p-5")}>
      <header className="space-y-3 border-b border-border pb-4">
        <div className="flex items-center gap-2">
          <span
            className="size-2 shrink-0 rounded-full ring-2 ring-offset-2 ring-offset-card"
            style={graphNodeAccentDotStyle(accentColor)}
          />
          <Badge variant="secondary" className="font-semibold uppercase tracking-wide">
            {groupedDisplaySelection
              ? inspectorCopy(loc, "groupedSelection")
              : attributes?.nodeType
                ? graphNodeTypeLabel(loc, attributes.nodeType)
                : inspectorCopy(loc, "entityDefault")}
          </Badge>
        </div>
        <h2
          className="line-clamp-2 text-lg font-semibold leading-snug break-words"
          title={String(attributes?.label ?? effectiveNodeId)}
        >
          {String(attributes?.label ?? effectiveNodeId)}
        </h2>
        <p className="font-mono text-xs break-all text-muted-foreground">
          {groupedDisplaySelection ? nodeId : effectiveNodeId}
        </p>
        {groupedDisplaySelection ? (
          <div className={inspectorNoticeClass}>
            <p className="mb-1.5 font-medium text-foreground">
              {inspectorCopy(loc, "groupedDisplayTitle")}
            </p>
            <p className="text-muted-foreground">
              {canActivateFocused
                ? inspectorCanonicalNodeLine(loc, effectiveNodeId)
                : focusedUnavailableReasonText(focusedUnavailableReason, loc)}
            </p>
          </div>
        ) : null}
        {(attributes?.valid_from || attributes?.valid_until || attribution.length > 0 || predictions.length > 0) ? (
          <div className="flex flex-wrap gap-1.5">
            {attributes?.valid_from || attributes?.valid_until ? (
              <Badge variant="outline" className="badge-status-warning">
                {inspectorCopy(loc, "temporalBadge")}
              </Badge>
            ) : null}
            {attribution.length ? (
              <Badge variant="outline">{inspectorBadgeCount(loc, attribution.length, "sourceFields")}</Badge>
            ) : null}
            {predictions.length ? (
              <Badge variant="outline">{inspectorBadgeCount(loc, predictions.length, "candidateLinks")}</Badge>
            ) : null}
            {isArchived ? (
              <Badge variant="outline" className="badge-status-warning">
                {inspectorCopy(loc, "archivedBadge")}
              </Badge>
            ) : null}
          </div>
        ) : null}
      </header>

      {(attributes?.valid_from || attributes?.valid_until) ? (
        <div className="rounded-lg border border-border bg-muted/35 px-3 py-2 font-mono text-xs text-foreground">
          {attributes?.valid_from ? (
            <div>{inspectorCopy(loc, "validFrom")}: {attributes.valid_from}</div>
          ) : null}
          {attributes?.valid_until ? (
            <div>{inspectorCopy(loc, "validUntil")}: {attributes.valid_until}</div>
          ) : null}
        </div>
      ) : null}

      {workspaceId && decisionsEnabled ? (
        <GraphInspectorDecisions
          workspaceId={workspaceId}
          nodeId={effectiveNodeId}
          enabled={decisionsEnabled}
          locale={loc}
        />
      ) : null}

      {evidenceLinks.length > 0 || workspaceId ? (
        <section className={inspectorSectionClass}>
          <h3 className={inspectorSectionTitleClass}>
            {inspectorCopy(loc, "knowledgeLinks")}
          </h3>
          <div className="flex flex-col gap-2">
            {workspaceId && provenanceEnabled ? (
              <Button variant="outline" size="sm" className="justify-start gap-2" asChild>
                <Link
                  to={`${workspacePath(workspaceId, 'lineage')}?node=${encodeURIComponent(effectiveNodeId)}`}
                >
                  <PublicIcon name="git-branch-01" size={14} className="shrink-0 opacity-70" />
                  {inspectorCopy(loc, "openLineage")}
                </Link>
              </Button>
            ) : null}
            {evidenceLinks.map((link) => (
              <Button key={link.to} variant="outline" size="sm" className="justify-start gap-2" asChild>
                <Link to={link.to}>
                  <PublicIcon name="link-external" size={14} className="shrink-0 opacity-70" />
                  {evidenceLinkLabel(link.kind)}
                </Link>
              </Button>
            ))}
          </div>
        </section>
      ) : null}

      {/* Canonical nodes remain editable even when their current body is empty. */}
      <details className={cn(graphNodePanelCollapse, "group/node")} open>
        <summary className={graphNodePanelSummary}>{inspectorCopy(loc, "content")}</summary>
        <div className={cn(graphNodePanelBody, "mt-2")}>
          <MarkdownContentViewer
            workspaceId={workspaceId}
            content={nodeContent}
            resource={{ kind: "context-node", id: effectiveNodeId }}
            allowEdit={graphWriteEnabled}
            onApplied={onMarkdownApplied}
            onDirtyChange={onMarkdownDirtyChange}
          />
        </div>
      </details>

      <section className={inspectorSectionClass}>
        <h3 className={inspectorSectionTitleClass}>{inspectorCopy(loc, "actions")}</h3>
        <div className="flex flex-col gap-2.5">
          {graphWriteEnabled ? (
            <Button
              type="button"
              className="w-full"
              onClick={onRunPredictions}
              disabled={isRunningPredictions || !actionNodeId}
            >
              {isRunningPredictions ? <PublicIcon name="loader-01" size={14} className="animate-spin" /> : null}
              {isRunningPredictions
                ? inspectorCopy(loc, "running")
                : inspectorCopy(loc, "runPrediction")}
            </Button>
          ) : null}
          {graphWriteEnabled && onArchiveNode && actionNodeId && !groupedDisplaySelection ? (
            <Button
              type="button"
              variant="destructive"
              className="w-full"
              disabled={isArchivingNode || isArchived}
              onClick={() => {
                const label = String(attributes?.label ?? effectiveNodeId);
                if (!window.confirm(fmt(inspectorCopy(loc, "archiveNodeConfirm"), { label }))) {
                  return;
                }
                void onArchiveNode(actionNodeId);
              }}
            >
              {isArchivingNode ? <PublicIcon name="loader-01" size={14} className="animate-spin" /> : null}
              {isArchivingNode
                ? inspectorCopy(loc, "archiveNodeRunning")
                : inspectorCopy(loc, "archiveNode")}
            </Button>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => onDownloadProvenance("json")} disabled={!actionNodeId}>
              {inspectorCopy(loc, "provenanceJson")}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => onDownloadProvenance("markdown")} disabled={!actionNodeId}>
              {inspectorCopy(loc, "provenanceMd")}
            </Button>
          </div>
        </div>
        {graphWriteEnabled ? (
          <Input
            value={predictionType}
            onChange={(event) => onPredictionTypeChange(event.target.value)}
            placeholder={inspectorCopy(loc, "predictionTypePlaceholder")}
            className="h-9 bg-background"
          />
        ) : null}
      </section>

      <section className={inspectorSectionClass}>
        <h3 className={inspectorSectionTitleClass}>{inspectorCopy(loc, "tracePath")}</h3>
        <Input
          value={pathTargetId}
          onChange={(event) => onPathTargetChange(event.target.value)}
          placeholder={inspectorCopy(loc, "pathTargetPlaceholder")}
          className="h-9 bg-background"
        />
        <Button type="button" variant="secondary" className="w-full sm:w-auto" onClick={onTracePath} disabled={!actionNodeId}>
          {inspectorCopy(loc, "traceCausalPath")}
        </Button>
        <Separator className="bg-border/80" />
        {pathResult?.path?.length ? (
          <>
            <PathFlowViz
              locale={loc}
              path={pathResult.path}
              edgeIds={pathResult.edge_ids}
              totalWeight={pathResult.total_weight}
              bottleneckNodeId={pathResult.bottleneck_node}
              onFocusNode={onFocusNode}
            />
            <PathDistanceIntelPanel locale={loc} result={pathResult} />
          </>
        ) : (
          <p className={inspectorEmptyClass}>
            {inspectorCopy(loc, "pathEmptyHint")}
          </p>
        )}
      </section>

      {/* Candidate Links */}
      <details className={cn(graphNodePanelCollapse, "group/node")} open={predictions.length > 0}>
        <summary className={graphNodePanelSummary}>{inspectorCopy(loc, "candidateLinks")}</summary>
        <div className={graphNodePanelBody}>
          {predictions.length > 0 ? (
            <div className="flex flex-col gap-2">
              {predictions.map((prediction) => (
                <Button
                  key={`${prediction.target}-${prediction.type}`}
                  type="button"
                  variant="ghost"
                  className="h-auto w-full justify-start rounded-lg border border-border bg-card px-3 py-2.5 text-left font-normal transition-colors hover:bg-muted/50"
                  onClick={() => onPathTargetChange(prediction.target)}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-foreground">{prediction.label || prediction.target}</div>
                      <div className="text-xs text-muted-foreground">
                        {graphNodeTypeLabel(loc, prediction.type)}
                      </div>
                    </div>
                    <Badge variant="secondary" className="shrink-0 tabular-nums">
                      {formatLocalePercent(loc, prediction.score, 1)}
                    </Badge>
                  </div>
                </Button>
              ))}
            </div>
          ) : isRunningPredictions ? (
            <div className="flex items-center gap-2 py-1 text-xs text-muted-foreground">
              <PublicIcon name="loader-01" size={13} className="animate-spin" />
              <span>{inspectorCopy(loc, "computingCandidates")}</span>
            </div>
          ) : (
            <p className={inspectorEmptyClass}>{inspectorCopy(loc, "runPredictionHint")}</p>
          )}
        </div>
      </details>

      {/* Source Attribution */}
      <details className={cn(graphNodePanelCollapse, "group/node")}>
        <summary className={graphNodePanelSummary}>{inspectorCopy(loc, "sourceAttribution")}</summary>
        <div className={graphNodePanelBody}>
          {attribution.length ? (
            <div className="flex flex-col gap-2">
              {attribution.map(({ key, value }) => (
                <div key={key} className={graphInspectorKv}>
                  <div className={graphInspectorKvKey}>{key}</div>
                  <div className={graphInspectorKvValue}>
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className={inspectorEmptyClass}>{inspectorCopy(loc, "noAttribution")}</p>
          )}
        </div>
      </details>

      {/* Properties */}
      <details className={cn(graphNodePanelCollapse, "group/node")}>
        <summary className={graphNodePanelSummary}>{inspectorCopy(loc, "properties")}</summary>
        <div className={graphNodePanelBody}>
          {propertyEntries.length ? (
            <div className="flex flex-col gap-2">
              {propertyEntries.map(([key, value]) => (
                <div key={key} className={graphInspectorKv}>
                  <div className={graphInspectorKvKey}>{key}</div>
                  <div className={graphInspectorKvValue}>
                    {typeof value === "object" ? JSON.stringify(value) : String(value)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className={inspectorEmptyClass}>{inspectorCopy(loc, "noProperties")}</p>
          )}
        </div>
      </details>
    </aside>
  );
}
