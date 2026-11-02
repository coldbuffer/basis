import { Button } from "@/components/ui/button.js";
import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { Label } from "@/components/ui/label.js";
import { Textarea } from "@/components/ui/textarea.js";
import { Switch } from "@/components/ui/switch.js";
import { cn } from "@/lib/utils.js";
import {
  exWsPaddedCol,
  exWsSplitSidebar,
  exWsTemplateSegmentBtn,
  exWsTemplateSegmentGroup,
} from "@/lib/ui-classes/ws-ui.js";
import { wsTextarea } from "@/lib/ui-classes/console-ws.js";
import { ReasoningRuleLibraryCombobox } from "./reasoning-rule-library-combobox.js";
import type { ReasoningRule } from "./reasoning-rules-dialog.js";
import { formatLocaleNumber } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import type { LocaleMessages } from "@/i18n/en.js";

type Copy = LocaleMessages['analyze']['reasoning'];

type TemplateKey = "drug" | "gene" | "pathway";

const TEMPLATE_ICONS: Record<TemplateKey, string> = {
  drug: "atom",
  gene: "tag",
  pathway: "path",
};

function SectionLabel({
  locale,
  id,
  title,
  count,
  icon,
}: {
  locale: Locale;
  id: string;
  title: string;
  count?: number;
  icon: string;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <PublicIcon name={icon} size={13} className="text-muted-foreground" />
      <h2 id={id} className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h2>
      {typeof count === "number" ? (
        <span className="font-mono text-[11px] tabular-nums text-foreground">
          {formatLocaleNumber(locale, count)}
        </span>
      ) : null}
    </div>
  );
}

export function ReasoningInputPanel({
  locale,
  copy,
  facts,
  factCount,
  onFactsChange,
  rules,
  draftRuleCount,
  libraryCount,
  factIssues,
  ruleIssues,
  onRulesChange,
  savedRules,
  runIncludedIds,
  onRunIncludedChange,
  onManageLibrary,
  onSaveDraft,
  canWriteGraph,
  onLoadDraftFromLibrary,
  onLoadTemplate,
  onLoadTypedFacts,
  loadingTypedFacts,
  templateButtons,
  canRun,
  isRunning,
  onRun,
  onReset,
  applyToGraph,
  onApplyToGraphChange,
}: {
  locale: Locale;
  copy: Copy;
  facts: string;
  factCount: number;
  onFactsChange: (v: string) => void;
  rules: string;
  draftRuleCount: number;
  libraryCount: number;
  factIssues: string[];
  ruleIssues: string[];
  onRulesChange: (v: string) => void;
  savedRules: ReasoningRule[];
  runIncludedIds: Set<string>;
  onRunIncludedChange: (ids: Set<string>) => void;
  onManageLibrary: () => void;
  onSaveDraft: () => void;
  canWriteGraph: boolean;
  onLoadDraftFromLibrary: (body: string) => void;
  onLoadTemplate: (key: TemplateKey) => void;
  onLoadTypedFacts: () => void;
  loadingTypedFacts: boolean;
  templateButtons: { key: TemplateKey; label: string }[];
  canRun: boolean;
  isRunning: boolean;
  onRun: () => void;
  onReset: () => void;
  applyToGraph: boolean;
  onApplyToGraphChange: (next: boolean) => void;
}) {
  return (
    <div className={exWsSplitSidebar}>
      <div className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-border px-4">
        <span className="flex items-center gap-1.5 text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          <PublicIcon name="shapes-01" size={13} />
          {copy.templates_title}
        </span>
        <div className={exWsTemplateSegmentGroup} role="group" aria-label={copy.templates_title}>
          {templateButtons.map(({ key, label }) => (
            <Button
              key={key}
              type="button"
              variant="ghost"
              size="sm"
              className={exWsTemplateSegmentBtn}
              onClick={() => onLoadTemplate(key)}
            >
              <PublicIcon name={TEMPLATE_ICONS[key]} size={12} />
              {label}
            </Button>
          ))}
        </div>
      </div>

      <div className={cn(exWsPaddedCol, "min-h-0 flex-1 gap-6 py-4")}>
        <section className="flex flex-col gap-2" aria-labelledby="reasoning-input-facts">
          <div className="flex items-center justify-between gap-2">
            <SectionLabel
              locale={locale}
              id="reasoning-input-facts"
              icon="file-01"
              title={copy.facts_title}
              count={factCount}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 shrink-0 text-[11px]"
              disabled={loadingTypedFacts}
              onClick={onLoadTypedFacts}
            >
              {copy.load_typed_facts}
            </Button>
          </div>
          <Textarea
            className={cn(wsTextarea, "min-h-[8.5rem] text-xs leading-relaxed")}
            value={facts}
            onChange={(e) => onFactsChange(e.target.value)}
            placeholder={copy.facts_placeholder}
            spellCheck={false}
            aria-label={copy.facts_title}
            aria-invalid={factIssues.length > 0}
          />
          {factIssues.length > 0 ? (
            <ul className="m-0 list-none space-y-0.5 p-0 text-[11px] text-destructive">
              {factIssues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          ) : null}
        </section>

        <section className="flex flex-col gap-2" aria-labelledby="reasoning-input-rules">
          <SectionLabel locale={locale} id="reasoning-input-rules" icon="git-branch-01" title={copy.rules_title} />
          {savedRules.length > 0 ? (
            <div className="flex flex-col gap-1.5">
              <SectionLabel
                locale={locale}
                id="reasoning-input-library"
                icon="book-01"
                title={copy.library_section}
                count={libraryCount}
              />
              <ReasoningRuleLibraryCombobox
                rules={savedRules}
                runIncludedIds={runIncludedIds}
                onRunIncludedChange={onRunIncludedChange}
                placeholder={copy.library_combobox_placeholder}
                emptySearchLabel={copy.library_combobox_empty}
                loadDraftLabel={copy.load_draft}
                onLoadDraft={onLoadDraftFromLibrary}
              />
            </div>
          ) : null}
          <div className="flex items-center justify-between gap-2">
            <SectionLabel
              locale={locale}
              id="reasoning-input-draft"
              icon="edit-01"
              title={copy.draft_section}
              count={draftRuleCount}
            />
            {canWriteGraph ? (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-[11px]"
                disabled={!rules.trim()}
                title={copy.save_draft_only}
                onClick={onSaveDraft}
              >
                <PublicIcon name="save-01" size={13} />
                {copy.save_to_library}
              </Button>
            ) : null}
          </div>
          <Textarea
            className={cn(wsTextarea, "min-h-[8.5rem] text-xs leading-relaxed")}
            value={rules}
            onChange={(e) => onRulesChange(e.target.value)}
            placeholder={copy.rules_placeholder}
            spellCheck={false}
            aria-label={copy.draft_section}
            aria-invalid={ruleIssues.length > 0}
          />
          {ruleIssues.length > 0 ? (
            <ul className="m-0 list-none space-y-0.5 p-0 text-[11px] text-destructive">
              {ruleIssues.map((issue) => <li key={issue}>{issue}</li>)}
            </ul>
          ) : null}
        </section>
      </div>

      <div className="flex shrink-0 items-center gap-2 border-t border-border px-4 py-3">
        <Button type="button" variant="outline" size="sm" className="h-8" onClick={onManageLibrary}>
          <PublicIcon name="book-01" size={14} />
          {copy.manage_rules}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="size-8"
          title={copy.reset}
          onClick={onReset}
        >
          <PublicIcon name="arrow-rotate-left-01" size={14} />
        </Button>
        <div
          className="ml-auto flex items-center gap-2"
          title={canWriteGraph ? (applyToGraph ? copy.write_graph_hint : copy.preview_only) : copy.write_graph_view_only}
        >
          <Switch
            id="reasoning-apply-graph"
            checked={applyToGraph && canWriteGraph}
            disabled={!canWriteGraph}
            onCheckedChange={onApplyToGraphChange}
          />
          <Label htmlFor="reasoning-apply-graph" className="flex cursor-pointer items-center gap-1 text-xs font-medium">
            <PublicIcon name={applyToGraph && canWriteGraph ? "graph" : "eye-open"} size={13} />
            {applyToGraph && canWriteGraph ? copy.write_graph : copy.preview_only}
          </Label>
        </div>
        <Button
          type="button"
          size="sm"
          className="h-8"
          disabled={isRunning || !canRun}
          onClick={onRun}
        >
          <PublicIcon name={isRunning ? "lightning-01" : "play-03"} size={14} className={isRunning ? "animate-pulse" : undefined} />
          {isRunning ? copy.running : copy.run}
        </Button>
      </div>
    </div>
  );
}
