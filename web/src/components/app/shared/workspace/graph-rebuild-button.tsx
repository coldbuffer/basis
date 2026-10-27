import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { SIDEBAR_ICON_BUTTON_CLASS, SidebarIcon } from '@/components/app/shared/shell/sidebar-icon.js';
import { useState } from 'react';
import { toast } from 'sonner';
import { ConfirmAlertDialog } from '@/components/app/shared/console/ConfirmAlertDialog.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { workspaceOpenApiPOST } from '@/lib/openapi/client.js';

type GraphRebuildMeta = {
  projection_revision?: number;
  projection_status?: string;
  node_count?: number;
  edge_count?: number;
};

export function GraphRebuildButton({
  workspaceId,
  onRebuilt,
  iconOnly = false,
}: {
  workspaceId: string;
  onRebuilt?: () => void;
  iconOnly?: boolean;
}) {
  const { t, locale } = useI18n();
  const w = t.graph.canvas.widgets;
  const [busy, setBusy] = useState(false);

  async function rebuild() {
    setBusy(true);
    try {
      const meta = await workspaceOpenApiPOST<GraphRebuildMeta>(workspaceId, 'graph/rebuild');
      const revision =
        typeof meta.projection_revision === 'number'
          ? meta.projection_revision
          : undefined;
      toast.success(
        w.rebuild_success,
        revision != null
          ? {
              description: fmt(w.rebuild_revision, {
                revision: formatLocaleNumber(locale as Locale, revision),
              }),
            }
          : undefined,
      );
      onRebuilt?.();
    } catch (err) {
      toast.error(formatUserFacingApiError(err, locale as Locale));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ConfirmAlertDialog
      title={w.rebuild_title}
      description={w.rebuild_description}
      confirmLabel={w.rebuild_confirm}
      destructive
      onConfirm={rebuild}
      trigger={
        <Button
          type="button"
          variant="outline"
          size={iconOnly ? "icon-sm" : "sm"}
          className={iconOnly ? SIDEBAR_ICON_BUTTON_CLASS : undefined}
          disabled={busy}
          aria-label={iconOnly ? w.rebuild_button : undefined}
          title={iconOnly ? w.rebuild_button : undefined}
        >
          {busy ? (
            <Spinner className={iconOnly ? "size-4" : "size-3.5"} />
          ) : iconOnly ? (
            <SidebarIcon name="sync" />
          ) : (
            <PublicIcon name="sync" className="size-3.5" />
          )}
          {iconOnly ? null : w.rebuild_button}
        </Button>
      }
    />
  );
}
