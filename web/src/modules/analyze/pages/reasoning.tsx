import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useI18n } from "@/i18n/context.js";
import { fmt, formatLocaleNumber, requestFailedStatusMessage } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { ReasoningRulesDialog, type ReasoningRule } from "./reasoning-rules-dialog.js";
import { ReasoningInputPanel } from "./reasoning-input.js";
import { ReasoningResultsPanel } from "./reasoning-results.js";
import { isReasoningFact, isReasoningRule, reasoningLineIssues } from "../i18n/reasoning-syntax.js";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog.js";
import { Button } from "@/components/ui/button.js";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog.js";
import { Input } from "@/components/ui/input.js";
import { Label } from "@/components/ui/label.js";
import { Checkbox } from "@/components/ui/checkbox.js";
import { workspaceOpenApiResponse } from '@/lib/openapi/client.js';
import { errorFromApiResponse } from "@/lib/errors/api-error.js";
import { useApiErrorMessage } from "@/lib/errors/use-api-error-message.js";
import { useWorkspaceCapabilitiesOptional } from "@/lib/workspace/capabilities.js";
import { exWsPageRow } from "@/lib/ui-classes/ws-ui.js";
import { workspaceOpenApiGET, workspaceOpenApiPOST } from '@/lib/openapi/client.js';

type SavedRule = ReasoningRule;

const SAMPLE_FACTS = `inhibits(Metformin, mTOR)
causes(mTOR, Neurodegeneration)
treats(Metformin, Diabetes)`;

const SAMPLE_RULE = `IF inhibits(Metformin, mTOR) AND causes(mTOR, Neurodegeneration) THEN candidate(Metformin, Alzheimer's)`;

const DEMO_PACK_MARKER = "demo_pack_id:";

function isDefaultReasoningSample(factsText: string, rulesText: string): boolean {
  return factsText === SAMPLE_FACTS && rulesText === SAMPLE_RULE;
}

const TEMPLATES = {
  drug: {
    facts: `inhibits(Metformin, mTOR)\ncauses(mTOR, Neurodegeneration)\ntreats(Metformin, Diabetes)`,
    rule: `IF inhibits(Metformin, mTOR) AND causes(mTOR, Neurodegeneration) THEN candidate(Metformin, Alzheimer's)`,
  },
  gene: {
    facts: `expressed_in(BRCA1, Breast)\nmutated_in(BRCA1, Cancer)\nassociated_with(Breast, Cancer)`,
    rule: `IF mutated_in(X, Cancer) AND expressed_in(X, Y) THEN risk_gene(X, Y)`,
  },
  pathway: {
    facts: `activates(EGF, EGFR)\ndownstream_of(MAPK, EGFR)\ndownstream_of(AKT, EGFR)`,
    rule: `IF activates(X, EGFR) AND downstream_of(Y, EGFR) THEN activates(X, Y)`,
  },
} as const;

export function ReasoningScreen({
  workspaceId,
}: {
  workspaceId: string;
}) {
  const apiError = useApiErrorMessage();
  const { t, locale } = useI18n();
  const copy = t.analyze.reasoning;
  const capsCtx = useWorkspaceCapabilitiesOptional();
  const canWriteGraph = !capsCtx?.loading && Boolean(capsCtx?.caps?.graph_write);
  const queryClient = useQueryClient();
  const [facts, setFacts] = useState(SAMPLE_FACTS);
  const [rules, setRules] = useState(SAMPLE_RULE);
  const [applyToGraph, setApplyToGraph] = useState(false);

  useEffect(() => {
    if (!canWriteGraph) {
      setApplyToGraph(false);
    }
  }, [canWriteGraph]);

  const [result, setResult] = useState<{
    inferred_facts?: string[];
    proof_chains?: Array<{ conclusion: string; rule: string; premises: string[] }>;
    rules_fired?: number;
    added_edges?: number;
    mutated?: boolean;
    derived_facts_persisted?: { created?: number; skipped?: number };
  } | null>(null);
  const [runSnapshot, setRunSnapshot] = useState<string | null>(null);
  const [pendingReplace, setPendingReplace] = useState<{
    facts: string;
    rules: string;
    clearLibrary: boolean;
  } | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const [savedRules, setSavedRules] = useState<SavedRule[]>([]);
  const [saveRuleName, setSaveRuleName] = useState("");
  const [savingRule, setSavingRule] = useState(false);
  const [saveRuleOpen, setSaveRuleOpen] = useState(false);
  const [manageRulesOpen, setManageRulesOpen] = useState(false);
  const [runIncludedIds, setRunIncludedIds] = useState<Set<string>>(() => new Set());
  const [saveIncludeInRun, setSaveIncludeInRun] = useState(false);
  const [loadingTypedFacts, setLoadingTypedFacts] = useState(false);
  const demoAutoLoadDoneRef = useRef<string | null>(null);

  const loadSavedRules = useCallback(async () => {
    if (!workspaceId) return;
    try {
      const data = await workspaceOpenApiGET<{ rules: SavedRule[] }>(workspaceId, "rules");
      const list = data.rules;
      setSavedRules(list);
      setRunIncludedIds((prev) => {
        const next = new Set<string>();
        for (const id of prev) {
          if (list.some((r) => r.id === id)) next.add(id);
        }
        return next;
      });
    } catch {
      setSavedRules([]);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadSavedRules();
  }, [loadSavedRules]);

  async function saveCurrentRules() {
    const name = saveRuleName.trim();
    const body = rules.trim();
    if (!name || !body || !workspaceId) return;
    setSavingRule(true);
    setError("");
    try {
      const created = await workspaceOpenApiPOST<{ rule: SavedRule }>(workspaceId, "rules", {
        body: { name, body, enabled: false },
      });
      if (saveIncludeInRun && created.rule?.id) {
        setRunIncludedIds((prev) => new Set(prev).add(created.rule.id));
      }
      setSaveRuleName("");
      setSaveIncludeInRun(false);
      setSaveRuleOpen(false);
      await loadSavedRules();
    } catch (e) {
      setError(apiError(e));
    } finally {
      setSavingRule(false);
    }
  }

  const factLines = useMemo(
    () => facts.split(/\r?\n/).map((l) => l.trim()).filter(Boolean),
    [facts],
  );

  const draftRuleLines = useMemo(
    () => rules.split(/\r?\n/).map((l) => l.trim()).filter(Boolean),
    [rules],
  );

  const libraryRuleLines = useMemo(
    () =>
      savedRules
        .filter((r) => runIncludedIds.has(r.id))
        .map((r) => r.body.trim())
        .filter(Boolean),
    [savedRules, runIncludedIds],
  );

  const runRules = useMemo(
    () => [...new Set([...libraryRuleLines, ...draftRuleLines])],
    [draftRuleLines, libraryRuleLines],
  );

  const formatFactIssue = useCallback(
    (n: number) => fmt(copy.fact_issue, { n: formatLocaleNumber(locale, n) }),
    [copy.fact_issue, locale],
  );
  const formatRuleIssue = useCallback(
    (n: number) => fmt(copy.rule_issue, { n: formatLocaleNumber(locale, n) }),
    [copy.rule_issue, locale],
  );
  const formatLibraryRuleIssue = useCallback(
    (name: string) => fmt(copy.library_rule_issue, { name }),
    [copy.library_rule_issue],
  );

  const factIssues = useMemo(
    () => reasoningLineIssues(factLines, isReasoningFact, formatFactIssue),
    [formatFactIssue, factLines],
  );

  const ruleIssues = useMemo(() => {
    const draftIssues = reasoningLineIssues(draftRuleLines, isReasoningRule, formatRuleIssue);
    const libraryIssues = savedRules
      .filter((rule) => runIncludedIds.has(rule.id))
      .flatMap((rule) => {
        const lines = rule.body.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
        return lines.length > 0 && lines.every(isReasoningRule) ? [] : [formatLibraryRuleIssue(rule.name)];
      });
    return [...libraryIssues, ...draftIssues].slice(0, 3);
  }, [draftRuleLines, formatLibraryRuleIssue, formatRuleIssue, runIncludedIds, savedRules]);

  const inputSignature = useMemo(
    () => JSON.stringify({ facts: factLines, rules: runRules }),
    [factLines, runRules],
  );
  const resultStale = Boolean(result && runSnapshot && runSnapshot !== inputSignature);
  const canRun = runRules.length > 0 && factIssues.length === 0 && ruleIssues.length === 0;

  const onRuleCreated = useCallback((ruleId: string, includeInRun: boolean) => {
    if (includeInRun) {
      setRunIncludedIds((prev) => new Set(prev).add(ruleId));
    }
  }, []);

  const handleRun = useCallback(async () => {
    if (!canRun) return;
    setIsRunning(true);
    setError("");
    const signature = inputSignature;
    try {
      const response = await workspaceOpenApiResponse('POST', workspaceId, 'reasoning/run', {
        body: {
          facts: factLines,
          rules: runRules,
          mode: "forward",
          apply_to_graph: applyToGraph && canWriteGraph,
        },
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw errorFromApiResponse(
          response.status,
          data,
          requestFailedStatusMessage(locale as Locale, response.status),
          locale as Locale,
        );
      }
      if (response.status === 207) setError(data.message || copy.partial_run);
      setResult(data);
      setRunSnapshot(signature);
      if (data.mutated) {
        queryClient.invalidateQueries({
          queryKey: workspaceId ? ["graph", "full-load", workspaceId] : ["graph", "full-load"],
        });
      }
    } catch (e) {
      setError(apiError(e));
    } finally {
      setIsRunning(false);
    }
  }, [apiError, applyToGraph, canRun, canWriteGraph, copy.partial_run, factLines, inputSignature, workspaceId, locale, queryClient, runRules]);

  const applyReplace = useCallback((next: { facts: string; rules: string; clearLibrary: boolean }) => {
    setFacts(next.facts);
    setRules(next.rules);
    if (next.clearLibrary) {
      setRunIncludedIds(new Set());
    }
    setError("");
    setPendingReplace(null);
  }, []);

  useEffect(() => {
    if (!workspaceId) return;
    if (demoAutoLoadDoneRef.current === workspaceId) return;
    if (!isDefaultReasoningSample(facts, rules)) return;

    let cancelled = false;
    void (async () => {
      try {
        const ws = await workspaceOpenApiGET<{ description?: string | null }>(workspaceId, "");
        if (cancelled) return;
        const description = (ws.description ?? "").trim();
        if (!description.includes(DEMO_PACK_MARKER)) return;
        demoAutoLoadDoneRef.current = workspaceId;
        if (!isDefaultReasoningSample(facts, rules)) return;

        const [ground, rulesPayload] = await Promise.all([
          workspaceOpenApiGET<{ facts: string[] }>(workspaceId, "reasoning/ground-facts"),
          workspaceOpenApiGET<{ rules: SavedRule[] }>(workspaceId, "rules"),
        ]);
        if (cancelled) return;
        if (!isDefaultReasoningSample(facts, rules)) return;

        const factsText = (ground.facts ?? []).join("\n");
        if (!factsText.trim()) return;

        const demoRule = rulesPayload.rules?.find((r) => r.body.includes("renewalOrderSignatory"));
        applyReplace({
          facts: factsText,
          rules: demoRule?.body ?? rules,
          clearLibrary: false,
        });
        if (demoRule?.id) {
          setRunIncludedIds(new Set([demoRule.id]));
        }
        await loadSavedRules();
      } catch {
        // User can load manually; avoid blocking the screen on auto-import.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [applyReplace, facts, loadSavedRules, rules, workspaceId]);

  const requestReplace = useCallback((next: { facts: string; rules: string; clearLibrary: boolean }) => {
    const unchanged = facts === next.facts
      && rules === next.rules
      && (!next.clearLibrary || runIncludedIds.size === 0);
    if (unchanged) {
      return;
    }
    if (!facts.trim() && !rules.trim() && runIncludedIds.size === 0) {
      applyReplace(next);
      return;
    }
    setPendingReplace(next);
  }, [applyReplace, facts, rules, runIncludedIds]);

  const loadTemplate = useCallback((key: keyof typeof TEMPLATES) => {
    const template = TEMPLATES[key];
    requestReplace({ facts: template.facts, rules: template.rule, clearLibrary: false });
  }, [requestReplace]);

  const loadTypedGroundFacts = useCallback(async () => {
    if (!workspaceId) return;
    setLoadingTypedFacts(true);
    setError("");
    try {
      const data = await workspaceOpenApiGET<{ facts: string[] }>(
        workspaceId,
        "reasoning/ground-facts",
      );
      const text = (data.facts ?? []).join("\n");
      if (!text.trim()) {
        setError(copy.load_typed_facts_empty);
        return;
      }
      requestReplace({ facts: text, rules, clearLibrary: false });
    } catch (e) {
      setError(apiError(e));
    } finally {
      setLoadingTypedFacts(false);
    }
  }, [apiError, copy.load_typed_facts_empty, requestReplace, rules, workspaceId]);

  const handleReset = useCallback(() => {
    requestReplace({ facts: SAMPLE_FACTS, rules: SAMPLE_RULE, clearLibrary: true });
  }, [requestReplace]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key !== "Enter") return;
      const target = event.target;
      if (target instanceof HTMLElement && target.closest("[role='dialog']")) return;
      event.preventDefault();
      void handleRun();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleRun]);

  const templateButtons = useMemo(
    () =>
      (["drug", "gene", "pathway"] as const).map((key) => ({
        key,
        label: copy.template_labels[key],
      })),
    [copy.template_labels],
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className={exWsPageRow}>
        <ReasoningInputPanel
          locale={locale as Locale}
          copy={copy}
          facts={facts}
          factCount={factLines.length}
          factIssues={factIssues}
          onFactsChange={setFacts}
          rules={rules}
          draftRuleCount={draftRuleLines.length}
          libraryCount={libraryRuleLines.length}
          ruleIssues={ruleIssues}
          onRulesChange={setRules}
          savedRules={savedRules}
          runIncludedIds={runIncludedIds}
          onRunIncludedChange={setRunIncludedIds}
          onManageLibrary={() => setManageRulesOpen(true)}
          onSaveDraft={() => setSaveRuleOpen(true)}
          canWriteGraph={canWriteGraph}
          onLoadDraftFromLibrary={(body) => {
            requestReplace({ facts, rules: body, clearLibrary: false });
          }}
          onLoadTemplate={loadTemplate}
          onLoadTypedFacts={() => void loadTypedGroundFacts()}
          loadingTypedFacts={loadingTypedFacts}
          templateButtons={templateButtons}
          canRun={canRun}
          isRunning={isRunning}
          onRun={() => void handleRun()}
          onReset={handleReset}
          applyToGraph={applyToGraph}
          onApplyToGraphChange={setApplyToGraph}
        />

        <ReasoningResultsPanel
          locale={locale}
          copy={copy}
          workspaceId={workspaceId}
          result={result}
          isRunning={isRunning}
          error={error}
          resultStale={resultStale}
          hasInput={factLines.length > 0 || runRules.length > 0}
        />
      </div>

      <ReasoningRulesDialog
        workspaceId={workspaceId}
        open={manageRulesOpen}
        onOpenChange={setManageRulesOpen}
        canWrite={canWriteGraph}
        rules={savedRules}
        onRuleCreated={onRuleCreated}
        onRulesChange={loadSavedRules}
        onLoadIntoEditor={(body) => {
          requestReplace({ facts, rules: body, clearLibrary: false });
        }}
      />

      <Dialog open={saveRuleOpen} onOpenChange={setSaveRuleOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{copy.save_title}</DialogTitle>
            <DialogDescription>{copy.save_desc}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label htmlFor="rule-save-name">{copy.save_name}</Label>
              <Input
                id="rule-save-name"
                value={saveRuleName}
                onChange={(e) => setSaveRuleName(e.target.value)}
                placeholder={copy.save_placeholder}
                maxLength={120}
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="rule-save-include-run"
                checked={saveIncludeInRun}
                onCheckedChange={(v) => setSaveIncludeInRun(v === true)}
              />
              <Label htmlFor="rule-save-include-run" className="cursor-pointer text-sm font-normal">
                {copy.save_include_run}
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setSaveRuleOpen(false)}>
              {t.core.common.cancel}
            </Button>
            <Button
              type="button"
              disabled={savingRule || !saveRuleName.trim() || !rules.trim()}
              onClick={() => void saveCurrentRules()}
            >
              {t.core.common.save}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={pendingReplace != null} onOpenChange={(open) => { if (!open) setPendingReplace(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{copy.replace_title}</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingReplace?.clearLibrary ? copy.reset_body : copy.replace_body}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t.core.common.cancel}</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (pendingReplace) applyReplace(pendingReplace);
              }}
            >
              {copy.replace_confirm}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
