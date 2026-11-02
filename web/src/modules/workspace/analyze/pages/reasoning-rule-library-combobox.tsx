import { useMemo } from "react";
import { Button } from "@/components/ui/button.js";
import {
  Combobox,
  ComboboxChip,
  ComboboxChips,
  ComboboxChipsInput,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxValue,
  useComboboxAnchor,
} from "@/components/ui/combobox.js";
import type { ReasoningRule } from "./reasoning-rules-dialog.js";
import { cn } from "@/lib/utils.js";
import { exWsHint } from "@/lib/ui-classes/ws-ui.js";

export type ReasoningRuleOption = Pick<ReasoningRule, "id" | "name" | "body">;

export function ReasoningRuleLibraryCombobox({
  rules,
  runIncludedIds,
  onRunIncludedChange,
  onLoadDraft,
  disabled,
  placeholder,
  emptySearchLabel,
  emptyLibraryLabel,
  loadDraftLabel,
  className,
}: {
  rules: ReasoningRuleOption[];
  runIncludedIds: Set<string>;
  onRunIncludedChange: (ids: Set<string>) => void;
  onLoadDraft?: (body: string) => void;
  disabled?: boolean;
  placeholder: string;
  emptySearchLabel: string;
  emptyLibraryLabel?: string;
  loadDraftLabel: string;
  className?: string;
}) {
  const anchor = useComboboxAnchor();

  const selected = useMemo(
    () => rules.filter((r) => runIncludedIds.has(r.id)),
    [rules, runIncludedIds],
  );

  if (rules.length === 0) {
    return emptyLibraryLabel ? <p className={exWsHint}>{emptyLibraryLabel}</p> : null;
  }

  return (
    <Combobox
      items={rules}
      multiple
      disabled={disabled}
      value={selected}
      onValueChange={(next) => {
        onRunIncludedChange(new Set(next.map((r) => r.id)));
      }}
      itemToStringLabel={(rule) => rule.name}
      isItemEqualToValue={(a, b) => a.id === b.id}
    >
      <ComboboxChips ref={anchor} className={cn("w-full", className)}>
        <ComboboxValue>
          {selected.map((rule) => (
            <ComboboxChip key={rule.id} aria-label={rule.name}>
              {rule.name}
            </ComboboxChip>
          ))}
        </ComboboxValue>
        <ComboboxChipsInput placeholder={placeholder} disabled={disabled} />
      </ComboboxChips>
      <ComboboxContent anchor={anchor} side="bottom" align="start">
        <ComboboxEmpty>{emptySearchLabel}</ComboboxEmpty>
        <ComboboxList>
          {(rule: ReasoningRuleOption) => (
            <ComboboxItem key={rule.id} value={rule} className="items-start py-2">
              <div className="min-w-0 flex-1 pr-2">
                <div className="truncate text-sm font-medium">{rule.name}</div>
                <div className="line-clamp-2 text-[10px] leading-snug text-muted-foreground">
                  {rule.body}
                </div>
              </div>
              {onLoadDraft ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 shrink-0 px-1.5 text-[10px] text-muted-foreground"
                  onPointerDown={(e) => e.preventDefault()}
                  onClick={(e) => {
                    e.stopPropagation();
                    onLoadDraft(rule.body);
                  }}
                >
                  {loadDraftLabel}
                </Button>
              ) : null}
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
