import { SidebarIcon } from "@/components/app/shared/shell/sidebar-icon.js";
import { cn } from "@/lib/utils.js";
import { GraphToolButton, GraphToolTower } from './graph-tool-tower.js';

export type GraphToolbarRailItem = {
  id: string;
  label: string;
  title?: string;
  active?: boolean;
  disabled?: boolean;
  icon?: string;
  ariaLabel?: string;
  onClick: () => void;
};

export type GraphToolbarRailGroup = {
  id: string;
  label?: string;
  items: GraphToolbarRailItem[];
};

function RailIcon({ icon }: { icon?: string }) {
  if (!icon) {
    return null;
  }
  return <SidebarIcon name={icon} />;
}

export function GraphToolbarRail({
  groups,
  expandLabels = "right",
  orientation = "vertical",
}: {
  groups: GraphToolbarRailGroup[];
  expandLabels?: "left" | "right";
  orientation?: "vertical" | "horizontal";
}) {
  const visible = groups.filter((group) => group.items.length > 0);
  if (!visible.length) {
    return null;
  }

  const alignEnd = expandLabels === "left";
  const horizontal = orientation === "horizontal";

  return (
    <div className={cn("flex gap-2", horizontal ? "flex-row items-start" : "flex-col", !horizontal && (alignEnd ? "items-end" : "items-start"))}>
      {visible.map((group) => (
        <div key={group.id} className={cn("flex gap-1", horizontal ? "flex-row" : "flex-col", !horizontal && (alignEnd ? "items-end" : "items-start"))}>
          <GraphToolTower orientation={orientation} expandLabels={expandLabels} aria-label={group.label ?? group.id}>
          {group.items.map((item) => (
            <GraphToolButton
              key={item.id}
              active={item.active}
              label={item.ariaLabel ?? item.label}
              icon={<RailIcon icon={item.icon} />}
              disabled={item.disabled}
              title={item.title}
              onClick={item.onClick}
            />
          ))}
          </GraphToolTower>
        </div>
      ))}
    </div>
  );
}
