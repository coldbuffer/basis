import { ConfirmAlertDialog } from '@/components/app/shared/console/ConfirmAlertDialog.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { resourceCardSurfaceClass } from '@/lib/ui-classes/card-surface.js';
import { useI18n } from '@/i18n/context.js';
import { ModelProviderIcon } from '@/components/admin/models/model-provider-icon.js';
import { cn } from '@/lib/utils.js';

export type ConfiguredProviderRow = {
  id: string;
  provider: string;
  api_base: string;
  configured: boolean;
};

type Props = {
  rows: ConfiguredProviderRow[];
  providerLabels: Record<string, string>;
  selectedId: string | null;
  busyId: string | null;
  onSelect: (row: ConfiguredProviderRow) => void;
  onAddNew: () => void;
  onRemove: (row: ConfiguredProviderRow) => void;
};

export function ConfiguredProvidersList({
  rows,
  providerLabels,
  selectedId,
  busyId,
  onSelect,
  onAddNew,
  onRemove,
}: Props) {
  const { t } = useI18n();
  const m = t.admin_models.page;

  function providerName(id: string) {
    return providerLabels[id] ?? id;
  }

  return (
    <section className="space-y-3 border-b border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{m.configured_providers_title}</h3>
        <Button type="button" size="sm" variant="outline" onClick={onAddNew}>
          {m.add_provider}
        </Button>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">{m.configured_providers_empty}</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li key={row.id}>
              <article
                className={cn(
                  resourceCardSurfaceClass,
                  'flex flex-wrap items-center justify-between gap-3 rounded-xl px-3.5 py-3',
                  selectedId === row.id && 'ring-1 ring-[var(--acc)]',
                )}
              >
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-start gap-2 text-left"
                  onClick={() => onSelect(row)}
                >
                  <ModelProviderIcon providerId={row.provider} size={20} className="mt-0.5" />
                  <span className="min-w-0">
                  <p className="font-medium">{providerName(row.provider)}</p>
                  {row.api_base ? (
                    <p className="truncate font-mono text-[12px] text-muted-foreground">
                      {row.api_base}
                    </p>
                  ) : null}
                  </span>
                </button>
                <div className="flex items-center gap-2">
                  <Badge
                    variant={row.configured ? 'outline' : 'secondary'}
                    className={row.configured ? 'badge-status-success' : undefined}
                  >
                    {row.configured ? m.configured : m.not_configured}
                  </Badge>
                  <ConfirmAlertDialog
                    title={m.remove_provider_title}
                    description={m.remove_provider_note.replace(
                      '{name}',
                      providerName(row.provider),
                    )}
                    destructive
                    onConfirm={() => onRemove(row)}
                    trigger={
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="text-destructive hover:text-destructive"
                        disabled={busyId === row.id}
                      >
                        {t.core.common.remove}
                      </Button>
                    }
                  />
                </div>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
