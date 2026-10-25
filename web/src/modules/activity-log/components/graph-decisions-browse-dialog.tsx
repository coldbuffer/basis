import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { useI18n } from '@/i18n/context.js';
import { GraphDecisionsList } from '@/modules/activity-log/components/graph-decisions-list.js';

export function GraphDecisionsBrowseDialog({
  workspaceId,
  open,
  onOpenChange,
  initialFilter = '',
  onSelectDecision,
}: {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialFilter?: string;
  onSelectDecision: (decisionId: string) => void;
}) {
  const { t } = useI18n();
  const al = t.activity_log.page;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,36rem)] max-w-lg flex-col gap-0 p-0 sm:max-w-xl">
        <DialogHeader className="border-b border-border px-4 py-3">
          <DialogTitle className="text-left text-base">{al.browse_decisions_title}</DialogTitle>
          <p className="text-left text-xs text-muted-foreground">{al.browse_decisions_hint}</p>
        </DialogHeader>
        <GraphDecisionsList
          workspaceId={workspaceId}
          enabled={open}
          initialFilter={initialFilter}
          onSelectDecision={(id) => {
            onSelectDecision(id);
            onOpenChange(false);
          }}
          className="min-h-0 flex-1"
        />
      </DialogContent>
    </Dialog>
  );
}
