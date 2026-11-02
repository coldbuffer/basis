import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.js";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs.js";
import { cn } from "@/lib/utils.js";

import type { GraphPluginPanelDescriptor } from '../lib/plugins/plugin-types.js';

export function GraphPluginPanelDialog({
  panels,
  activePanelId,
  onActivePanelChange,
  onClosePanel,
}: {
  panels: GraphPluginPanelDescriptor[];
  activePanelId: string | null;
  onActivePanelChange: (panelId: string) => void;
  onClosePanel: (panelId: string) => void;
}) {
  const open = panels.length > 0;
  const resolvedActiveId =
    activePanelId && panels.some((panel) => panel.id === activePanelId)
      ? activePanelId
      : panels[0]?.id ?? "";

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && resolvedActiveId) {
          onClosePanel(resolvedActiveId);
        }
      }}
    >
      <DialogContent
        className={cn(
          "flex max-h-[min(85vh,720px)] flex-col gap-0 overflow-hidden p-0 sm:max-w-lg md:max-w-xl",
        )}
      >
        {panels.length > 1 ? (
          <Tabs
            value={resolvedActiveId}
            onValueChange={onActivePanelChange}
            className="flex min-h-0 flex-1 flex-col gap-0"
          >
            <DialogHeader className="shrink-0 border-b px-6 pt-6 pb-0 text-left">
              <TabsList variant="line" className="h-auto w-full flex-wrap justify-start gap-1 bg-transparent p-0">
                {panels.map((panel) => (
                  <TabsTrigger key={panel.id} value={panel.id} className="text-sm">
                    {panel.title}
                  </TabsTrigger>
                ))}
              </TabsList>
            </DialogHeader>
            {panels.map((panel) => (
              <TabsContent
                key={panel.id}
                value={panel.id}
                className="min-h-0 flex-1 overflow-y-auto px-6 py-4 hud-scrollbar focus-visible:outline-none"
              >
                {panel.content}
              </TabsContent>
            ))}
          </Tabs>
        ) : (
          <>
            <DialogHeader className="shrink-0 border-b px-6 py-4 text-left">
              <DialogTitle>{panels[0]?.title}</DialogTitle>
            </DialogHeader>
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4 hud-scrollbar">
              {panels[0]?.content}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
