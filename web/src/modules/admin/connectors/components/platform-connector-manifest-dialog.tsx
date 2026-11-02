import { useCallback, useEffect, useMemo, useState } from 'react';
import { JsonEditor } from '@/components/app/shared/primitives/json-editor.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Label } from '@/components/ui/label.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Switch } from '@/components/ui/switch.js';
import { useI18n } from '@/i18n/context.js';
import { fmt } from '@/i18n/format.js';
import { openApiGET } from '@/lib/openapi/client.js';
import { downloadTextBlob } from '@/lib/admin/download-text-blob.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';

type ManifestDialogProps = {
  service: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  platformEnabled: boolean;
  allowAll: boolean;
  onPlatformEnabledChange: (service: string, enabled: boolean) => void | Promise<void>;
};

type ManifestResponse = {
  service: string;
  platform_enabled: boolean;
  connector: Record<string, unknown>;
};

export function PlatformConnectorManifestDialog({
  service,
  open,
  onOpenChange,
  platformEnabled,
  allowAll,
  onPlatformEnabledChange,
}: ManifestDialogProps) {
  const { t } = useI18n();
  const ps = t.admin_settings.page.connectors;
  const formatApiError = useApiErrorMessage();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<ManifestResponse | null>(null);
  const [toggling, setToggling] = useState(false);

  const load = useCallback(async () => {
    if (!service) return;
    setLoading(true);
    setError(null);
    try {
      const body = await openApiGET<ManifestResponse>(
        `/api/v1/settings/connectors/catalog/${encodeURIComponent(service)}`,
      );
      setPayload(body);
    } catch (err) {
      setError(formatApiError(err));
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [formatApiError, service]);

  useEffect(() => {
    if (open && service) {
      void load();
    } else if (!open) {
      setPayload(null);
      setError(null);
    }
  }, [load, open, service]);

  const displayName =
    (payload?.connector?.display_name as string | undefined) ?? service ?? '';

  const streamSummaries = useMemo(() => {
    if (!payload?.connector) return [];
    const streams = payload.connector.streams;
    if (!Array.isArray(streams)) return [];
    return streams
      .slice(0, 12)
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const rec = item as Record<string, unknown>;
        const name = String(rec.name ?? rec.stream_name ?? '');
        const label = String(rec.display_name ?? name);
        return name ? { name, label } : null;
      })
      .filter((x): x is { name: string; label: string } => x !== null);
  }, [payload]);

  const toolSummaries = useMemo(() => {
    if (!payload?.connector) return [];
    const tools = payload.connector.tools;
    if (!Array.isArray(tools)) return [];
    return tools
      .slice(0, 12)
      .map((item) => {
        if (!item || typeof item !== 'object') return null;
        const rec = item as Record<string, unknown>;
        const id = String(rec.id ?? '');
        const name = String(rec.name ?? id);
        return id ? { id, name } : null;
      })
      .filter((x): x is { id: string; name: string } => x !== null);
  }, [payload]);

  async function handleToggle(enabled: boolean) {
    if (!service) return;
    setToggling(true);
    try {
      await onPlatformEnabledChange(service, enabled);
    } finally {
      setToggling(false);
    }
  }

  function downloadManifestJson() {
    if (!payload || !service) return;
    downloadTextBlob(
      `bocp-${service}-manifest.json`,
      JSON.stringify(payload.connector, null, 2),
      'application/json;charset=utf-8',
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,52rem)] max-w-3xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="shrink-0 space-y-2 border-b border-border px-6 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <DialogTitle className="text-left">{displayName}</DialogTitle>
            <Badge variant={platformEnabled ? 'secondary' : 'outline'}>
              {platformEnabled ? ps.detail_enabled_badge : ps.detail_disabled_badge}
            </Badge>
          </div>
          <DialogDescription className="font-mono text-xs">
            {service ? fmt(ps.detail_service_key, { service }) : ''}
          </DialogDescription>
          {service && !loading && !error ? (
            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-2">
                <Switch
                  id="manifest-platform-enabled"
                  checked={platformEnabled}
                  disabled={toggling}
                  onCheckedChange={(checked) => void handleToggle(checked === true)}
                  data-testid="manifest-platform-enabled-switch"
                />
                <Label htmlFor="manifest-platform-enabled" className="text-sm font-normal">
                  {ps.detail_platform_enable_label}
                </Label>
              </div>
              {allowAll && platformEnabled ? (
                <p className="text-xs text-muted-foreground">{ps.detail_allow_all_hint}</p>
              ) : null}
            </div>
          ) : null}
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
              <Spinner className="size-4" />
              {ps.detail_loading}
            </div>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : payload ? (
            <div className="space-y-4">
              {(streamSummaries.length > 0 || toolSummaries.length > 0) && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {streamSummaries.length > 0 ? (
                    <div className="rounded-md border border-border bg-muted/20 p-3">
                      <p className="text-xs font-medium text-foreground">{ps.detail_streams_title}</p>
                      <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                        {streamSummaries.map((s) => (
                          <li key={s.name} className="font-mono">
                            {s.name}
                            {s.label !== s.name ? ` — ${s.label}` : ''}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {toolSummaries.length > 0 ? (
                    <div className="rounded-md border border-border bg-muted/20 p-3">
                      <p className="text-xs font-medium text-foreground">{ps.detail_tools_title}</p>
                      <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                        {toolSummaries.map((tool) => (
                          <li key={tool.id} className="font-mono">
                            {tool.id}
                            {tool.name !== tool.id ? ` — ${tool.name}` : ''}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              )}
              <JsonEditor
                height={360}
                readOnly
                value={JSON.stringify(payload.connector, null, 2)}
              />
            </div>
          ) : null}
        </div>
        <DialogFooter className="shrink-0 border-t border-border px-6 py-3 sm:justify-between">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!payload}
            onClick={() => downloadManifestJson()}
          >
            {ps.download_manifest_json}
          </Button>
          <Button type="button" size="sm" variant="secondary" onClick={() => onOpenChange(false)}>
            {ps.detail_close}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
