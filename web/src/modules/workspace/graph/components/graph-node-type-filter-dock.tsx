import { useState } from "react";

import { Button } from "@/components/ui/button.js";
import { Checkbox } from "@/components/ui/checkbox.js";
import { Input } from "@/components/ui/input.js";
import { SIDEBAR_ICON_BUTTON_CLASS, SidebarIcon } from "@/components/app/shared/shell/sidebar-icon.js";
import { fmt, formatLocaleNumber } from "@/i18n/format.js";
import { cn } from "@/lib/utils.js";

import type { GraphEdgeTypeCount } from '../lib/graph-edge-types.js';
import type { GraphNodeTypeCount } from '../lib/graph-node-types.js';
import { GraphLoadBudgetControl } from "./graph-load-budget-control";
import type { GraphCatalogTotals, GraphLoadBudget } from '../lib/graph-load-budget.js';
import { graphCopy, graphNodeKindLabel, type GraphScreenLocale } from '../i18n/screen-copy.js';

type TypeCount = {
  type: string;
  count: number;
};

function TypeFilterSection({
  locale,
  heading,
  items,
  hiddenTypes,
  labelFor,
  onHiddenTypesChange,
  idPrefix,
  search,
  fill,
}: {
  locale: GraphScreenLocale;
  heading: string;
  items: TypeCount[];
  hiddenTypes: ReadonlySet<string>;
  labelFor: (type: string) => string;
  onHiddenTypesChange: (types: string[]) => void;
  idPrefix: string;
  search?: {
    query: string;
    onQueryChange: (query: string) => void;
    placeholder: string;
  };
  fill?: boolean;
}) {
  const query = search?.query.trim().toLocaleLowerCase() ?? "";
  const visibleItems = query
    ? items.filter((item) => labelFor(item.type).toLocaleLowerCase().includes(query))
    : items;
  const allVisible = visibleItems.every((item) => !hiddenTypes.has(item.type));

  const setTypeVisible = (type: string, visible: boolean) => {
    const hidden = new Set(hiddenTypes);
    if (visible) hidden.delete(type);
    else hidden.add(type);
    onHiddenTypesChange([...hidden]);
  };

  const setScopeVisible = (visible: boolean) => {
    const hidden = new Set(hiddenTypes);
    for (const item of visibleItems) {
      if (visible) hidden.delete(item.type);
      else hidden.add(item.type);
    }
    onHiddenTypesChange([...hidden]);
  };

  return (
    <section className="flex flex-col gap-2">
      <div className={fill ? "sticky top-0 z-10 flex flex-col gap-2 bg-background pb-1" : "flex flex-col gap-2"}>
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-medium">{heading}</h3>
          {visibleItems.length > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => setScopeVisible(!allVisible)}
            >
              {graphCopy(locale, allVisible ? "nodeTypeHideAll" : "nodeTypeShowAll")}
            </Button>
          ) : null}
        </div>
        {search ? (
          <Input
            value={search.query}
            onChange={(event) => search.onQueryChange(event.target.value)}
            placeholder={search.placeholder}
            aria-label={search.placeholder}
            className="h-8"
          />
        ) : null}
      </div>
      {visibleItems.length > 0 ? (
        <ul className="flex flex-col">
          {visibleItems.map((item) => {
            const label = labelFor(item.type);
            const visible = !hiddenTypes.has(item.type);
            const id = `${idPrefix}-${encodeURIComponent(item.type)}`;
            return (
              <li key={item.type}>
                <div className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/60">
                  <Checkbox
                    id={id}
                    checked={visible}
                    onCheckedChange={(checked) => setTypeVisible(item.type, checked === true)}
                  />
                  <label htmlFor={id} className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
                    <span className="min-w-0 flex-1 truncate">{label}</span>
                    <span className="tabular-nums text-xs text-muted-foreground">
                      {fmt(graphCopy(locale, "nodeTypeCount"), {
                        count: formatLocaleNumber(locale, item.count),
                      })}
                    </span>
                  </label>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="px-2 py-3 text-sm text-muted-foreground">{graphCopy(locale, "nodeTypeFilterEmpty")}</p>
      )}
    </section>
  );
}

export function GraphNodeTypeFilterDock({
  locale,
  open,
  onOpenChange,
}: {
  locale: GraphScreenLocale;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="icon-sm"
      aria-expanded={open}
      aria-pressed={open}
      aria-controls="graph-type-filter-sidebar"
      aria-label={graphCopy(locale, "nodeTypeFilterAria")}
      title={graphCopy(locale, "nodeTypeFilterAria")}
      onClick={() => onOpenChange(!open)}
      className={cn(
        SIDEBAR_ICON_BUTTON_CLASS,
        open && "bg-[color-mix(in_oklch,var(--foreground)_10%,var(--control))]",
      )}
    >
      <SidebarIcon name="sliders" />
    </Button>
  );
}

export function GraphNodeTypeFilterSidebar({
  locale,
  items,
  hiddenTypes,
  onHiddenTypesChange,
  edgeItems,
  hiddenEdgeTypes,
  onHiddenEdgeTypesChange,
  onClose,
  loadBudget,
}: {
  locale: GraphScreenLocale;
  items: GraphNodeTypeCount[];
  hiddenTypes: ReadonlySet<string>;
  onHiddenTypesChange: (types: string[]) => void;
  edgeItems: GraphEdgeTypeCount[];
  hiddenEdgeTypes: ReadonlySet<string>;
  onHiddenEdgeTypesChange: (types: string[]) => void;
  onClose: () => void;
  loadBudget?: {
    budget: GraphLoadBudget;
    onBudgetCommit: (budget: GraphLoadBudget) => void;
    loadedNodes: number;
    loadedEdges: number;
    catalogTotals: GraphCatalogTotals;
    disabled?: boolean;
  };
}) {
  const [edgeQuery, setEdgeQuery] = useState("");

  return (
    <aside
      id="graph-type-filter-sidebar"
      className="explore-filter-shell border-l border-border bg-background"
      aria-label={graphCopy(locale, "nodeTypeFilterAria")}
    >
      <header className="flex shrink-0 items-center justify-between gap-2 px-4 pt-3 pr-2 pb-2">
        <h2 className="text-sm font-medium">{graphCopy(locale, "nodeTypeFilterTitle")}</h2>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          className={SIDEBAR_ICON_BUTTON_CLASS}
          onClick={onClose}
          aria-label={graphCopy(locale, "searchDismiss")}
        >
          <SidebarIcon name="x-02" />
        </Button>
      </header>
      {loadBudget ? (
        <div className="shrink-0 border-b border-border px-2 pt-1 pb-4">
          <GraphLoadBudgetControl
            locale={locale}
            budget={loadBudget.budget}
            onBudgetCommit={loadBudget.onBudgetCommit}
            loadedNodes={loadBudget.loadedNodes}
            loadedEdges={loadBudget.loadedEdges}
            catalogTotals={loadBudget.catalogTotals}
            disabled={loadBudget.disabled}
          />
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-2 pb-4">
        {items.length > 0 ? (
          <TypeFilterSection
            locale={locale}
            heading={graphCopy(locale, "nodeTypeFilterHeading")}
            items={items}
            hiddenTypes={hiddenTypes}
            labelFor={(type) => graphNodeKindLabel(locale, type)}
            onHiddenTypesChange={onHiddenTypesChange}
            idPrefix="node"
          />
        ) : null}
        {edgeItems.length > 0 ? (
          <TypeFilterSection
            locale={locale}
            heading={graphCopy(locale, "edgeTypeFilterHeading")}
            items={edgeItems}
            hiddenTypes={hiddenEdgeTypes}
            labelFor={(type) => type}
            onHiddenTypesChange={onHiddenEdgeTypesChange}
            idPrefix="edge"
            fill
            search={{
              query: edgeQuery,
              onQueryChange: setEdgeQuery,
              placeholder: graphCopy(locale, "edgeTypeFilterSearch"),
            }}
          />
        ) : null}
      </div>
    </aside>
  );
}
