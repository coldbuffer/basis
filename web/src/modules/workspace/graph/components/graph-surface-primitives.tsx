/** Graph canvas surfaces — Tailwind via `@/lib/ui-classes/sem-ui.js`. */
import type { ReactNode } from "react";
import {
  semInspector,
  semSurface,
  semSurfaceBody,
  semSurfaceBodyTight,
  semSurfaceSubtle,
} from "@/lib/ui-classes/sem-ui.js";

type SurfaceTone = "default" | "subtle" | "accent";
type SurfacePadding = "default" | "tight" | "none";

function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function SurfaceCard({
  children,
  tone = "default",
  padding = "default",
  className,
}: {
  children: ReactNode;
  tone?: SurfaceTone;
  padding?: SurfacePadding;
  className?: string;
}) {
  return (
    <div
      className={cx(
        semSurface,
        tone === "subtle" && semSurfaceSubtle,
        className,
      )}
    >
      {padding === "none" ? (
        children
      ) : (
        <div className={cx(semSurfaceBody, padding === "tight" && semSurfaceBodyTight)}>
          {children}
        </div>
      )}
    </div>
  );
}

export function InspectorPanel({
  children,
  open = true,
  className,
}: {
  children: ReactNode;
  open?: boolean;
  className?: string;
}) {
  return (
    <SurfaceCard className={cx(semInspector, open ? "block" : "hidden", className)} padding="none">
      {children}
    </SurfaceCard>
  );
}
