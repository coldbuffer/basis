import { SIDEBAR_ICON_BUTTON_CLASS, SidebarIcon } from "@/components/app/shared/shell/sidebar-icon.js";
import { useEffect, useRef, type ReactNode } from "react";

import { Button } from "@/components/ui/button.js";
import {
  InputGroup,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group.js";
import { graphCopy, type GraphScreenLocale } from '../i18n/screen-copy.js';

function KeywordFilterBar({
  locale,
  value,
  disabled,
  onChange,
}: {
  locale: GraphScreenLocale;
  value: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const isEditing = target?.matches("input, textarea, select, [contenteditable='true']");
      if (event.key === "/" && !isEditing && !disabled) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, [disabled]);

  const trimmed = value.trim();

  return (
    <div className="explore-search-dock-search relative min-w-0">
      <InputGroup className="h-9">
        <InputGroupInput
          ref={inputRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={graphCopy(locale, "searchPlaceholder")}
          aria-label={graphCopy(locale, "searchNodesAria")}
          aria-keyshortcuts="/"
          disabled={disabled}
        />
        {trimmed ? (
          <InputGroupButton
            type="button"
            size="icon-sm"
            className={SIDEBAR_ICON_BUTTON_CLASS}
            aria-label={graphCopy(locale, "searchClearAria")}
            onClick={() => onChange("")}
          >
            <SidebarIcon name="x-02" />
          </InputGroupButton>
        ) : (
          <InputGroupButton
            type="button"
            size="icon-sm"
            className={SIDEBAR_ICON_BUTTON_CLASS}
            tabIndex={-1}
            aria-hidden
            disabled
          >
            <SidebarIcon name="search-01" />
          </InputGroupButton>
        )}
      </InputGroup>
    </div>
  );
}

export function GraphSearchDock({
  locale = "en",
  query,
  onQueryChange,
  filterDisabled,
  trailingActions,
  infoMessage,
}: {
  locale?: GraphScreenLocale;
  query: string;
  onQueryChange: (value: string) => void;
  filterDisabled: boolean;
  trailingActions?: ReactNode;
  infoMessage?: string;
}) {
  return (
    <div className="flex w-max shrink-0 flex-col gap-2">
      <div className="explore-search-dock-toolbar flex w-max items-center gap-2">
        <KeywordFilterBar
          locale={locale}
          value={query}
          disabled={filterDisabled}
          onChange={onQueryChange}
        />
        {trailingActions ? (
          <div className="explore-search-dock-actions flex shrink-0 items-center gap-1.5">
            {trailingActions}
          </div>
        ) : null}
      </div>

      {infoMessage ? (
        <div className="text-xs text-muted-foreground" role="status">{infoMessage}</div>
      ) : null}
    </div>
  );
}
