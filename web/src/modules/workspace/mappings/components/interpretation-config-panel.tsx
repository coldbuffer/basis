import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Label } from '@/components/ui/label.js';
import { Textarea } from '@/components/ui/textarea.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { workspaceOpenApiGET, workspaceOpenApiPUT } from '@/lib/openapi/client.js';

type InterpretationResponse = {
  interpretation: { entity_type_surface_phrases: string[] };
};

function phrasesToText(phrases: string[]): string {
  return phrases.join('\n');
}

function textToPhrases(text: string): string[] {
  return text
    .split(/\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

export function InterpretationConfigPanel({
  workspaceId,
  canEdit,
  onSaved,
}: {
  workspaceId: string;
  canEdit: boolean;
  onSaved?: () => void;
}) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const copy = t.mappings.page.interpretation;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [phrasesText, setPhrasesText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await workspaceOpenApiGET<InterpretationResponse>(
        workspaceId,
        'governance/interpretation',
      );
      setPhrasesText(phrasesToText(body.interpretation.entity_type_surface_phrases ?? []));
    } catch (err) {
      setError(formatUserFacingApiError(err, loc));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, loc]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await workspaceOpenApiPUT<InterpretationResponse>(workspaceId, 'governance/interpretation', {
        body: { entity_type_surface_phrases: textToPhrases(phrasesText) },
      });
      toast.success(copy.toast_saved);
      await refresh();
      onSaved?.();
    } catch (err) {
      const message = formatUserFacingApiError(err, loc);
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3" data-testid="interpretation-config-panel">
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" />
          {t.core.common.loading}
        </div>
      ) : (
        <>
          <div className="space-y-2">
            <Label htmlFor="interpretation-type-phrases" className="text-xs">
              {copy.phrases_label}
            </Label>
            <Textarea
              id="interpretation-type-phrases"
              rows={8}
              className="font-mono text-xs"
              placeholder={copy.phrases_placeholder}
              value={phrasesText}
              disabled={!canEdit}
              onChange={(event) => setPhrasesText(event.target.value)}
            />
            <p className="text-[11px] text-muted-foreground">{copy.phrases_hint}</p>
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {canEdit ? (
            <Button type="button" size="sm" className="h-8" disabled={saving} onClick={() => void save()}>
              {saving ? t.core.common.loading : t.core.common.save}
            </Button>
          ) : null}
        </>
      )}
    </div>
  );
}

export function InterpretationConfigDialog({
  workspaceId,
  canEdit,
  open,
  onOpenChange,
  onSaved,
}: {
  workspaceId: string;
  canEdit: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => void;
}) {
  const { t } = useI18n();
  const copy = t.mappings.page.interpretation;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[min(90vh,32rem)] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>{copy.description}</DialogDescription>
        </DialogHeader>
        <InterpretationConfigPanel workspaceId={workspaceId} canEdit={canEdit} onSaved={onSaved} />
      </DialogContent>
    </Dialog>
  );
}
