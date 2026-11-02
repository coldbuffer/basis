import { createContext, forwardRef, useContext, type ButtonHTMLAttributes, type ReactNode } from "react";

import { Button } from "@/components/ui/button.js";
import { SIDEBAR_ICON_BUTTON_CLASS } from "@/components/app/shared/shell/sidebar-icon.js";
import { cn } from "@/lib/utils.js";

type GraphToolTowerLayout = {
  expandLabels: "left" | "right";
  orientation: "vertical" | "horizontal";
};

const GraphToolTowerContext = createContext<GraphToolTowerLayout>({
  expandLabels: "right",
  orientation: "vertical",
});

/** Vertical tool group on the graph canvas (Utopia / onto-style expand-on-hover labels). */
export function GraphToolTower({
  className,
  expandLabels = "right",
  orientation = "vertical",
  children,
}: {
  className?: string;
  /** `left`: labels grow toward the canvas (right-side rails). */
  expandLabels?: "left" | "right";
  orientation?: "vertical" | "horizontal";
  children: ReactNode;
}) {
  return (
    <GraphToolTowerContext.Provider value={{ expandLabels, orientation }}>
      <div
        className={cn(
          "group flex overflow-hidden rounded-md border border-border bg-background/95 shadow-none backdrop-blur-sm",
          orientation === "horizontal" ? "flex-row" : "flex-col",
          className,
        )}
      >
        {children}
      </div>
    </GraphToolTowerContext.Provider>
  );
}

export const GraphToolButton = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & {
    active?: boolean;
    label: string;
    icon: ReactNode;
  }
>(function GraphToolButton(
  { active, label, icon, className, type = "button", ...props },
  ref,
) {
  const { expandLabels, orientation } = useContext(GraphToolTowerContext);
  const expandLeft = expandLabels === "left";

  return (
    <Button
      ref={ref}
      type={type}
      variant="ghost"
      title={label}
      aria-label={label}
      className={cn(
        "h-auto gap-0 rounded-none p-2 text-sm font-normal text-muted-foreground shadow-none transition-[color,background-color] duration-150",
        "hover:bg-transparent dark:hover:bg-transparent",
        SIDEBAR_ICON_BUTTON_CLASS,
        "hover:not-disabled:text-foreground hover:not-disabled:bg-[color-mix(in_oklch,var(--foreground)_6%,var(--background))]",
        "focus-visible:outline-2 focus-visible:outline-ring focus-visible:-outline-offset-2 focus-visible:ring-0",
        "disabled:cursor-default disabled:opacity-45",
        active && "bg-[color-mix(in_oklch,var(--foreground)_10%,var(--background))] text-foreground",
        expandLeft && "w-full flex-row-reverse justify-start",
        expandLeft && orientation === "horizontal" && "w-auto",
        className,
      )}
      {...props}
    >
      {icon}
      <span
        className={cn(
          "max-w-0 overflow-hidden leading-none whitespace-nowrap opacity-0 transition-[max-width,margin,opacity] duration-200 ease-out motion-reduce:transition-none",
          "group-hover:max-w-36 group-hover:opacity-100 group-focus-within:max-w-36 group-focus-within:opacity-100",
          expandLeft
            ? "text-right group-hover:mr-2 group-focus-within:mr-2"
            : "group-hover:ml-2 group-focus-within:ml-2",
        )}
      >
        {label}
      </span>
    </Button>
  );
});
