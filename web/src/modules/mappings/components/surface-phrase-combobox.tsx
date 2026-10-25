import { useEffect, useMemo, useRef, useState } from 'react';
import { Input } from '@/components/ui/input.js';
import { cn } from '@/lib/utils.js';

type SurfacePhraseComboboxProps = {
  phrases: string[];
  value: string;
  onValueChange: (value: string) => void;
  disabled?: boolean;
  placeholder: string;
  emptySearchLabel: string;
  emptyPhrasesLabel: string;
  className?: string;
};

/** Inline searchable list (no portal) so wheel scroll works inside Radix Dialog. */
export function SurfacePhraseCombobox({
  phrases,
  value,
  onValueChange,
  disabled,
  placeholder,
  emptySearchLabel,
  emptyPhrasesLabel,
  className,
}: SurfacePhraseComboboxProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(value);

  useEffect(() => {
    if (!open) setQuery(value);
  }, [open, value]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return phrases;
    return phrases.filter((phrase) => phrase.toLowerCase().includes(needle));
  }, [phrases, query]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      const root = rootRef.current;
      if (!root || root.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('pointerdown', onPointerDown);
    return () => document.removeEventListener('pointerdown', onPointerDown);
  }, [open]);

  if (phrases.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyPhrasesLabel}</p>;
  }

  const displayValue = open ? query : value;

  return (
    <div ref={rootRef} className={cn('relative w-full', className)}>
      <Input
        value={displayValue}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        onFocus={() => {
          setQuery(value);
          setOpen(true);
        }}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setOpen(false);
            setQuery(value);
            return;
          }
          if (event.key === 'Enter' && open) {
            event.preventDefault();
            if (filtered.length === 1) {
              const picked = filtered[0];
              onValueChange(picked);
              setQuery(picked);
              setOpen(false);
            }
          }
        }}
      />
      {open ? (
        <div
          className="absolute top-full z-[200] mt-1 max-h-56 w-full overflow-y-auto overscroll-y-contain rounded-md border border-border bg-popover p-1 text-popover-foreground shadow-md"
          role="listbox"
        >
          {filtered.length === 0 ? (
            <p className="px-2 py-2 text-center text-sm text-muted-foreground">{emptySearchLabel}</p>
          ) : (
            filtered.map((phrase) => {
              const selected = phrase === value;
              return (
                <button
                  key={phrase}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={cn(
                    'flex w-full rounded-sm px-2 py-1.5 text-left font-mono text-xs outline-none hover:bg-accent hover:text-accent-foreground',
                    selected && 'bg-accent/60',
                  )}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onValueChange(phrase);
                    setQuery(phrase);
                    setOpen(false);
                  }}
                >
                  {phrase}
                </button>
              );
            })
          )}
        </div>
      ) : null}
    </div>
  );
}
