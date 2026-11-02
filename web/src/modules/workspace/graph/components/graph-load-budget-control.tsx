import { useEffect, useRef, useState } from "react";

import { Slider } from "@/components/ui/slider.js";
import { fmt, formatLocaleNumber } from "@/i18n/format.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";

import type { GraphScreenLocale } from '../i18n/screen-copy.js';
import {
  GRAPH_LOAD_BUDGET_MIN_EDGES,
  GRAPH_LOAD_BUDGET_MIN_NODES,
  catalogEdgeCeiling,
  catalogNodeCeiling,
  loadBudgetSliderBounds,
  snapLoadBudgetValue,
  type GraphCatalogTotals,
  type GraphLoadBudget,
} from '../lib/graph-load-budget.js';

function loadBudgetCopy(locale: GraphScreenLocale) {
  return messagesForLocale(locale).graph.canvas.load_budget;
}

export function GraphLoadBudgetControl({
  locale = "en",
  budget,
  onBudgetCommit,
  loadedNodes,
  loadedEdges,
  catalogTotals,
  disabled = false,
}: {
  locale?: GraphScreenLocale;
  budget: GraphLoadBudget;
  onBudgetCommit: (budget: GraphLoadBudget) => void;
  loadedNodes: number;
  loadedEdges: number;
  catalogTotals: GraphCatalogTotals;
  disabled?: boolean;
}) {
  const lb = loadBudgetCopy(locale);
  const [draftNodes, setDraftNodes] = useState(budget.maxNodes);
  const [draftEdges, setDraftEdges] = useState(budget.maxEdges);
  const draggingRef = useRef<"nodes" | "edges" | null>(null);

  const nodeMax = catalogNodeCeiling(catalogTotals);
  const edgeMax = catalogEdgeCeiling(catalogTotals);
  const nodeBounds = loadBudgetSliderBounds(nodeMax, GRAPH_LOAD_BUDGET_MIN_NODES);
  const edgeBounds = loadBudgetSliderBounds(edgeMax, GRAPH_LOAD_BUDGET_MIN_EDGES);
  const nodeValue = snapLoadBudgetValue(draftNodes, nodeBounds);
  const edgeValue = snapLoadBudgetValue(draftEdges, edgeBounds);

  useEffect(() => {
    if (draggingRef.current) return;
    setDraftNodes(budget.maxNodes);
    setDraftEdges(budget.maxEdges);
  }, [budget.maxEdges, budget.maxNodes]);

  const commitDraft = (nodes: number, edges: number) => {
    onBudgetCommit({ maxNodes: nodes, maxEdges: edges });
  };

  return (
    <section className="flex flex-col gap-3 px-2" aria-label={lb.aria_label}>
      <div className="flex flex-col gap-1">
        <h3 className="text-sm font-medium">{lb.title}</h3>
        <p className="text-xs leading-snug text-muted-foreground">{lb.hint}</p>
        <p className="text-xs text-muted-foreground">
          {fmt(lb.summary, {
            nLoaded: formatLocaleNumber(locale, loadedNodes),
            nMax: formatLocaleNumber(locale, nodeMax),
            eLoaded: formatLocaleNumber(locale, loadedEdges),
            eMax: formatLocaleNumber(locale, edgeMax),
          })}
        </p>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{lb.nodes_label}</span>
          <span className="tabular-nums font-medium">
            {formatLocaleNumber(locale, nodeValue)}
            <span className="font-normal text-muted-foreground">
              {" "}/ {formatLocaleNumber(locale, nodeMax)}
            </span>
          </span>
        </div>
        <Slider
          min={nodeBounds.min}
          max={nodeBounds.max}
          step={nodeBounds.step}
          value={[nodeValue]}
          disabled={disabled || nodeBounds.disabled}
          aria-label={lb.nodes_label}
          onValueChange={(values) => {
            draggingRef.current = "nodes";
            const next = values[0];
            if (typeof next === "number") setDraftNodes(next);
          }}
          onValueCommit={(values) => {
            draggingRef.current = null;
            const next = values[0];
            if (typeof next === "number") commitDraft(next, edgeValue);
          }}
        />
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">{lb.edges_label}</span>
          <span className="tabular-nums font-medium">
            {formatLocaleNumber(locale, edgeValue)}
            <span className="font-normal text-muted-foreground">
              {" "}/ {formatLocaleNumber(locale, edgeMax)}
            </span>
          </span>
        </div>
        <Slider
          min={edgeBounds.min}
          max={edgeBounds.max}
          step={edgeBounds.step}
          value={[edgeValue]}
          disabled={disabled || edgeBounds.disabled}
          aria-label={lb.edges_label}
          onValueChange={(values) => {
            draggingRef.current = "edges";
            const next = values[0];
            if (typeof next === "number") setDraftEdges(next);
          }}
          onValueCommit={(values) => {
            draggingRef.current = null;
            const next = values[0];
            if (typeof next === "number") commitDraft(nodeValue, next);
          }}
        />
      </div>

      {catalogTotals.nodeTotal != null && catalogTotals.edgeTotal != null ? (
        <p className="text-xs text-muted-foreground">
          {fmt(lb.catalog_full, {
            nodes: formatLocaleNumber(locale, catalogTotals.nodeTotal),
            edges: formatLocaleNumber(locale, catalogTotals.edgeTotal),
          })}
        </p>
      ) : null}
    </section>
  );
}
