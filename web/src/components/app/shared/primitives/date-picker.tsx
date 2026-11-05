"use client";

import * as React from "react";
import type { Matcher } from "react-day-picker";

import { Button } from "@/components/ui/button.js";
import { Calendar } from "@/components/ui/calendar.js";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover.js";
import { PublicIcon } from "@/components/app/shared/primitives/public-icon.js";
import { useI18n } from "@/i18n/context.js";
import { formatLocaleDateTime } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import { cn } from "@/lib/utils.js";

/**
 * shadcn Date Picker (composition): Popover + Calendar.
 * @see https://ui.shadcn.com/docs/components/base/date-picker
 */
export function DatePicker({
  value,
  onChange,
  placeholder,
  disabled = false,
  disabledMatchers,
  defaultMonth,
  startMonth,
  endMonth,
  captionLayout = "dropdown",
  className,
  align = "start",
  id,
  testId,
}: {
  value?: Date;
  onChange?: (date: Date | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
  disabledMatchers?: Matcher | Matcher[];
  defaultMonth?: Date;
  /** Limits month/year dropdowns (react-day-picker navigation bounds). */
  startMonth?: Date;
  endMonth?: Date;
  captionLayout?: React.ComponentProps<typeof Calendar>["captionLayout"];
  className?: string;
  align?: React.ComponentProps<typeof PopoverContent>["align"];
  id?: string;
  testId?: string;
}) {
  const { locale, t } = useI18n();
  const loc = locale as Locale;
  const [open, setOpen] = React.useState(false);
  const emptyLabel = placeholder ?? t.graph.diff.pick_date;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          id={id}
          data-testid={testId}
          variant="outline"
          disabled={disabled}
          data-empty={!value}
          className={cn(
            "w-full justify-start gap-2 text-left font-normal data-[empty=true]:text-muted-foreground",
            className,
          )}
        >
          <PublicIcon name="calendar-01" size={16} className="shrink-0 opacity-70" />
          {value ? formatLocaleDateTime(loc, value, { dateStyle: "medium" }) : emptyLabel}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align={align}>
        <Calendar
          mode="single"
          captionLayout={captionLayout}
          selected={value}
          defaultMonth={defaultMonth ?? value}
          startMonth={startMonth}
          endMonth={endMonth}
          disabled={disabledMatchers}
          onSelect={(selected) => {
            onChange?.(selected);
            setOpen(false);
          }}
        />
      </PopoverContent>
    </Popover>
  );
}
