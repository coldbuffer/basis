import { useCallback, useEffect, useId, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Label } from '@/components/ui/label.js';
import { Slider } from '@/components/ui/slider.js';
import { useI18n } from '@/i18n/context.js';
import { fmt, formatLocaleFixedDecimals } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { workspaceOpenApiGET } from '@/lib/openapi/client.js';
import { workspacePath } from '@/lib/nav/nav-config.js';

export type GovernanceScanOptions = {
  include_shacl: boolean;
  include_low_confidence: boolean;
  include_entity_label_clusters: boolean;
  include_graph_dedup: boolean;
  confidence_min: number;
  dedup_threshold: number;
};

type GovernanceConfig = {
  governor_confidence_min: number;
  governance_ontology_uri?: string | null;
};

const DEFAULT_DEDUP_THRESHOLD = 0.8;

function ScopeOption({
  checked,
  onCheckedChange,
  title,
  hint,
  extra,
  params,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  title: string;
  hint: string;
  extra?: ReactNode;
  params?: ReactNode;
}) {
  const checkboxId = useId();

  return (
    <div className="rounded-md border border-border">
      <div className="flex items-start gap-2.5 px-3 py-2">
        <Checkbox
          id={checkboxId}
          checked={checked}
          onCheckedChange={(v) => onCheckedChange(v === true)}
          className="mt-0.5"
        />
        <div className="min-w-0 flex-1">
          <label htmlFor={checkboxId} className="block cursor-pointer">
            <span className="text-sm font-medium">{title}</span>
            <span className="mt-0.5 block text-[11px] text-muted-foreground">{hint}</span>
          </label>
          {checked && extra ? <div className="mt-1">{extra}</div> : null}
        </div>
      </div>
      {checked && params ? (
        <div
          className="border-t border-border px-3 py-2 pl-10"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={(event) => event.stopPropagation()}
        >
          {params}
        </div>
      ) : null}
    </div>
  );
}

export function GovernanceScanDialog({
  workspaceId,
  open,
  onOpenChange,
  busy,
  onRun,
}: {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  busy: boolean;
  onRun: (options: GovernanceScanOptions) => void | Promise<void>;
}) {
  const { locale, t } = useI18n();
  const loc = locale as Locale;
  const g = t.review.governance_scan;
  const emptyCell = t.core.common.emptyCell;
  const confidenceSliderId = useId();
  const dedupSliderId = useId();

  const [configLoading, setConfigLoading] = useState(false);
  const [ontologyUri, setOntologyUri] = useState<string | null>(null);
  const [includeShacl, setIncludeShacl] = useState(true);
  const [includeLowConfidence, setIncludeLowConfidence] = useState(true);
  const [includeLabelClusters, setIncludeLabelClusters] = useState(true);
  const [includeGraphDedup, setIncludeGraphDedup] = useState(true);
  const [confidenceMin, setConfidenceMin] = useState(0.75);
  const [dedupThreshold, setDedupThreshold] = useState(DEFAULT_DEDUP_THRESHOLD);

  const loadConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const body = await workspaceOpenApiGET<{ config?: GovernanceConfig }>(
        workspaceId,
        'governance/config',
      );
      const cfg = body.config;
      if (cfg) {
        setConfidenceMin(cfg.governor_confidence_min ?? 0.75);
        setOntologyUri(cfg.governance_ontology_uri ?? null);
      }
    } finally {
      setConfigLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    if (!open) return;
    void loadConfig();
  }, [loadConfig, open]);

  const anyScope =
    includeShacl || includeLowConfidence || includeLabelClusters || includeGraphDedup;

  const handleRun = () => {
    if (!anyScope) return;
    void onRun({
      include_shacl: includeShacl,
      include_low_confidence: includeLowConfidence,
      include_entity_label_clusters: includeLabelClusters,
      include_graph_dedup: includeGraphDedup,
      confidence_min: confidenceMin,
      dedup_threshold: dedupThreshold,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{g.dialog_title}</DialogTitle>
          <DialogDescription>{g.dialog_desc}</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-2">
            <p className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              {g.scope_heading}
            </p>
            <div className="space-y-2.5">
              <ScopeOption
                checked={includeShacl}
                onCheckedChange={setIncludeShacl}
                title={g.scope_shacl}
                hint={g.scope_shacl_hint}
                extra={
                  <span className="block font-mono text-[10px] text-muted-foreground">
                    {fmt(g.hub_ontology_line, {
                      uri: ontologyUri?.trim() || emptyCell,
                    })}
                    {' · '}
                    <Link
                      to={workspacePath(workspaceId, 'settings')}
                      className="text-foreground underline-offset-2 hover:underline"
                      onClick={(event) => event.stopPropagation()}
                    >
                      {g.open_settings}
                    </Link>
                  </span>
                }
              />

              <ScopeOption
                checked={includeLowConfidence}
                onCheckedChange={setIncludeLowConfidence}
                title={g.scope_low_confidence}
                hint={g.scope_low_confidence_hint}
                params={
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2 text-[11px]">
                      <Label htmlFor={confidenceSliderId}>{g.confidence_min_label}</Label>
                      <span className="font-mono font-semibold text-primary">
                        {formatLocaleFixedDecimals(loc, confidenceMin, 2)}
                      </span>
                    </div>
                    <Slider
                      id={confidenceSliderId}
                      min={0.5}
                      max={0.99}
                      step={0.01}
                      value={[confidenceMin]}
                      disabled={configLoading || busy}
                      onValueChange={(value) => setConfidenceMin(value[0] ?? confidenceMin)}
                    />
                  </div>
                }
              />

              <ScopeOption
                checked={includeLabelClusters}
                onCheckedChange={setIncludeLabelClusters}
                title={g.scope_label_clusters}
                hint={g.scope_label_clusters_hint}
              />

              <ScopeOption
                checked={includeGraphDedup}
                onCheckedChange={setIncludeGraphDedup}
                title={g.scope_graph_dedup}
                hint={g.scope_graph_dedup_hint}
                params={
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2 text-[11px]">
                      <Label htmlFor={dedupSliderId}>{g.dedup_threshold_label}</Label>
                      <span className="font-mono font-semibold text-primary">
                        {fmt(g.dedup_threshold_percent, {
                          percent: formatLocaleFixedDecimals(loc, dedupThreshold * 100, 0),
                        })}
                      </span>
                    </div>
                    <Slider
                      id={dedupSliderId}
                      min={0.5}
                      max={0.99}
                      step={0.01}
                      value={[dedupThreshold]}
                      disabled={busy}
                      onValueChange={(value) => setDedupThreshold(value[0] ?? dedupThreshold)}
                    />
                    <p className="text-[10px] text-muted-foreground">{g.dedup_threshold_hint}</p>
                  </div>
                }
              />
            </div>
          </div>

          {!anyScope ? (
            <p className="text-[11px] text-destructive">{g.scope_required}</p>
          ) : null}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" disabled={busy} onClick={() => onOpenChange(false)}>
            {t.core.common.cancel}
          </Button>
          <Button type="button" disabled={busy || !anyScope} onClick={handleRun}>
            {busy ? g.running : g.run}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
