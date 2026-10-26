import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button.js';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import { Switch } from '@/components/ui/switch.js';
import { Spinner } from '@/components/ui/spinner.js';
import { useI18n } from '@/i18n/context.js';
import {
  fmt,
  formatLocaleDateTime,
  formatLocaleFixedDecimals,
  formatLocaleNumber,
} from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { formatUserFacingApiError } from '@/lib/errors/api-error-message.js';
import { workspaceOpenApiGET, workspaceOpenApiPUT } from '@/lib/openapi/client.js';
import { workspacePath, workspaceReviewPath } from '@/lib/nav/nav-config.js';
import { workspaceOntologyHubPath } from '@/modules/analyze/lib/hub-route.js';

function workspaceQualityScanPath(workspaceId: string): string {
  return `${workspacePath(workspaceId, 'quality')}?tab=scan`;
}

type GovernanceConfig = {
  governor_enabled: boolean;
  governor_interval_minutes: number;
  governor_confidence_min: number;
  governor_last_run_at?: string | null;
  governance_ontology_uri?: string | null;
  vocabulary_alignment_requires_review?: boolean;
};

type GovernanceConfigDraft = GovernanceConfig;

type GovernanceConfigResponse = {
  config: GovernanceConfig;
};

export function GovernanceConfigPanel({
  workspaceId,
  canEdit,
  showDataQualityLink = true,
}: {
  workspaceId: string;
  canEdit: boolean;
  /** Hide self-link when already on the data quality page. */
  showDataQualityLink?: boolean;
}) {
  const { t, locale } = useI18n();
  const loc = locale as Locale;
  const g = t.settings.panel.governance;
  const emptyCell = t.core.common.emptyCell;
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<GovernanceConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [draft, setDraft] = useState<GovernanceConfigDraft | null>(null);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await workspaceOpenApiGET<GovernanceConfigResponse>(workspaceId, 'governance/config');
      setConfig(body.config);
    } catch (err) {
      setError(formatUserFacingApiError(err, loc));
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }, [workspaceId, loc]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function openEdit() {
    if (!config) return;
    setDraft({ ...config });
    setEditOpen(true);
  }

  async function saveEdit() {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      const body = await workspaceOpenApiPUT<GovernanceConfigResponse>(workspaceId, 'governance/config', {
        body: {
          governor_enabled: draft.governor_enabled,
          governor_interval_minutes: draft.governor_interval_minutes,
          governor_confidence_min: draft.governor_confidence_min,
          governance_ontology_uri: draft.governance_ontology_uri ?? '',
          vocabulary_alignment_requires_review: Boolean(draft.vocabulary_alignment_requires_review),
        },
      });
      setConfig(body.config);
      setEditOpen(false);
      toast.success(g.toast_saved);
    } catch (err) {
      const message = formatUserFacingApiError(err, loc);
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle className="text-base">{g.title}</CardTitle>
            <CardDescription className="mt-1">{g.description}</CardDescription>
          </div>
          {canEdit && config ? (
            <Button type="button" size="sm" variant="outline" onClick={openEdit}>
              {t.settings.panel.edit}
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {loading ? (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Spinner className="size-4" />
              {t.core.common.loading}
            </div>
          ) : error && !config ? (
            <p className="text-destructive">{error}</p>
          ) : config ? (
            <>
              <p>
                <span className="text-muted-foreground">{g.scheduled_label}{t.settings.panel.label_suffix}</span>
                {config.governor_enabled ? g.enabled_on : g.enabled_off}
              </p>
              <p>
                <span className="text-muted-foreground">{g.interval_label}{t.settings.panel.label_suffix}</span>
                {fmt(g.interval_minutes, {
                  minutes: formatLocaleNumber(loc, config.governor_interval_minutes),
                })}
              </p>
              <p>
                <span className="text-muted-foreground">{g.confidence_label}{t.settings.panel.label_suffix}</span>
                {formatLocaleFixedDecimals(loc, config.governor_confidence_min, 2)}
              </p>
              <p>
                <span className="text-muted-foreground">{g.last_run_label}{t.settings.panel.label_suffix}</span>
                {config.governor_last_run_at
                  ? formatLocaleDateTime(loc, config.governor_last_run_at)
                  : emptyCell}
              </p>
              <p>
                <span className="text-muted-foreground">{g.ontology_uri_label}{t.settings.panel.label_suffix}</span>
                {config.governance_ontology_uri?.trim() ? config.governance_ontology_uri : emptyCell}
              </p>
              <p>
                <span className="text-muted-foreground">{g.vocabulary_alignment_review_label}{t.settings.panel.label_suffix}</span>
                {config.vocabulary_alignment_requires_review ? g.enabled_on : g.enabled_off}
              </p>
              <p className="text-[11px] leading-snug text-muted-foreground">
                {g.type_phrases_hint}{' '}
                <Link
                  to={workspaceOntologyHubPath(workspaceId, 'statement')}
                  className="text-foreground underline-offset-2 hover:underline"
                >
                  {g.type_phrases_link}
                </Link>
              </p>
              <p className="text-[11px] leading-snug text-muted-foreground">
                {g.manual_hint}{' '}
                <Link to={workspaceReviewPath(workspaceId)} className="text-foreground underline-offset-2 hover:underline">
                  {g.review_link}
                </Link>
                {g.manual_hint_suffix}
              </p>
              {showDataQualityLink ? (
                <p className="text-[11px] leading-snug text-muted-foreground">
                  <Link to={workspaceQualityScanPath(workspaceId)} className="text-foreground underline-offset-2 hover:underline">
                    {g.data_quality_link}
                  </Link>
                </p>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>

      {draft ? (
        <Dialog open={editOpen} onOpenChange={setEditOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{g.edit_title}</DialogTitle>
              <DialogDescription>{g.edit_desc}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div className="flex items-center justify-between gap-3">
                <Label htmlFor="gov-enabled">{g.scheduled_label}</Label>
                <Switch
                  id="gov-enabled"
                  checked={draft.governor_enabled}
                  onCheckedChange={(checked) =>
                    setDraft((current) => (current ? { ...current, governor_enabled: checked } : current))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="gov-interval">{g.interval_label}</Label>
                <Input
                  id="gov-interval"
                  type="number"
                  min={0}
                  max={10080}
                  value={draft.governor_interval_minutes}
                  onChange={(event) =>
                    setDraft((current) =>
                      current
                        ? {
                            ...current,
                            governor_interval_minutes: Number.parseInt(event.target.value, 10) || 0,
                          }
                        : current,
                    )
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="gov-confidence">{g.confidence_label}</Label>
                <Input
                  id="gov-confidence"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={draft.governor_confidence_min}
                  onChange={(event) =>
                    setDraft((current) =>
                      current
                        ? {
                            ...current,
                            governor_confidence_min: Number.parseFloat(event.target.value) || 0,
                          }
                        : current,
                    )
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="gov-ontology-uri">{g.ontology_uri_label}</Label>
                <Input
                  id="gov-ontology-uri"
                  type="text"
                  placeholder="https://…"
                  value={draft.governance_ontology_uri ?? ''}
                  onChange={(event) =>
                    setDraft((current) =>
                      current ? { ...current, governance_ontology_uri: event.target.value } : current,
                    )
                  }
                />
                <p className="text-[11px] text-muted-foreground">{g.ontology_uri_hint}</p>
              </div>
              <div className="flex items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <Label htmlFor="gov-valign-review">{g.vocabulary_alignment_review_label}</Label>
                  <p className="text-[11px] text-muted-foreground">{g.vocabulary_alignment_review_hint}</p>
                </div>
                <Switch
                  id="gov-valign-review"
                  checked={Boolean(draft.vocabulary_alignment_requires_review)}
                  onCheckedChange={(checked) =>
                    setDraft((current) =>
                      current ? { ...current, vocabulary_alignment_requires_review: checked } : current,
                    )
                  }
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditOpen(false)}>
                {t.core.common.cancel}
              </Button>
              <Button type="button" disabled={saving} onClick={() => void saveEdit()}>
                {saving ? t.core.common.loading : t.core.common.save}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </>
  );
}
