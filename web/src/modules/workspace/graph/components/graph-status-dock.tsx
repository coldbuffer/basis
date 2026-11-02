import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge.js";
import type { GraphLoadPhase } from '../lib/types.js';
import { getGraphLoadTitle } from '../lib/graph-loading.js';
import {
  type GraphScreenLocale,
  graphActiveCountLabel,
  graphCopy,
  graphStatusCounts,
} from '../i18n/screen-copy.js';

function StatusBadge({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "warm" | "success";
}) {
  const className =
    tone === "success" ? "badge-status-success" : tone === "warm" ? "badge-status-warning" : undefined;
  return (
    <Badge variant={tone === "default" ? "secondary" : "outline"} className={className}>
      {children}
    </Badge>
  );
}

export type GraphStatusSummary = {
  nodeCount: number;
  edgeCount: number;
};

export function GraphStatusDock({
  locale = "en",
  showLoadingStatus,
  loadingPhase,
  summary,
  activeNodeCount,
  focusedSummary,
  readOnly = false,
  trailing,
}: {
  locale?: GraphScreenLocale;
  showLoadingStatus: boolean;
  loadingPhase?: GraphLoadPhase;
  summary: GraphStatusSummary | null | undefined;
  activeNodeCount: number | null | undefined;
  focusedSummary: string | null;
  readOnly?: boolean;
  trailing?: ReactNode;
}) {
  const hasLoading = showLoadingStatus && loadingPhase;
  const hasSummary = Boolean(summary);
  const hasActive = typeof activeNodeCount === "number" && Number.isFinite(activeNodeCount);
  const hasFocused = Boolean(focusedSummary);

  if (!hasLoading && !hasSummary && !hasActive && !hasFocused && !readOnly && !trailing) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {readOnly ? (
        <StatusBadge tone="warm">{graphCopy(locale, "viewerReadOnly")}</StatusBadge>
      ) : null}
      {hasLoading && loadingPhase ? (
        <StatusBadge>{getGraphLoadTitle(loadingPhase, locale)}</StatusBadge>
      ) : null}
      {summary ? (
        <StatusBadge>
          {graphStatusCounts(locale, summary.nodeCount, summary.edgeCount)}
        </StatusBadge>
      ) : null}
      {hasActive ? (
        <StatusBadge tone="success">{graphActiveCountLabel(locale, activeNodeCount!)}</StatusBadge>
      ) : null}
      {focusedSummary ? <StatusBadge tone="warm">{focusedSummary}</StatusBadge> : null}
      {trailing}
    </div>
  );
}
