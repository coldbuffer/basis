import { fmt, formatLocaleNumber } from "@/i18n/format.js";
import type { Locale } from "@/i18n/locale.js";
import type { AnyLocaleMessages } from "@/i18n/pick-locale.js";

type CompareLocale = AnyLocaleMessages["ontology"]["hub"]["versions"]["compare_summary"];

type ChangeBucket = {
  added?: unknown[];
  removed?: unknown[];
  changed?: unknown[];
};

export type VersionComparePayload = {
  version1?: string;
  version2?: string;
  comparison_mode?: string;
  class_changes?: ChangeBucket;
  property_changes?: ChangeBucket;
  individual_changes?: ChangeBucket;
  edge_changes?: ChangeBucket;
  axiom_changes?: { added_count?: number; removed_count?: number };
};

function countList(bucket: ChangeBucket | undefined, key: "added" | "removed" | "changed"): number {
  const raw = bucket?.[key];
  return Array.isArray(raw) ? raw.length : 0;
}

function line(
  locale: Locale,
  template: string,
  count: number,
): string | null {
  if (count <= 0) return null;
  return fmt(template, { count: formatLocaleNumber(locale, count) });
}

export function VersionCompareSummary({
  data,
  locale,
  labels,
}: {
  data: VersionComparePayload;
  locale: Locale;
  labels: CompareLocale;
}) {
  const rows: string[] = [];
  const push = (text: string | null) => {
    if (text) rows.push(text);
  };

  push(line(locale, labels.classes_added, countList(data.class_changes, "added")));
  push(line(locale, labels.classes_removed, countList(data.class_changes, "removed")));
  push(line(locale, labels.classes_changed, countList(data.class_changes, "changed")));
  push(line(locale, labels.properties_added, countList(data.property_changes, "added")));
  push(line(locale, labels.properties_removed, countList(data.property_changes, "removed")));
  push(line(locale, labels.properties_changed, countList(data.property_changes, "changed")));
  push(line(locale, labels.individuals_added, countList(data.individual_changes, "added")));
  push(line(locale, labels.individuals_removed, countList(data.individual_changes, "removed")));
  push(line(locale, labels.edges_added, countList(data.edge_changes, "added")));
  push(line(locale, labels.edges_removed, countList(data.edge_changes, "removed")));

  const axiom = data.axiom_changes;
  if (axiom) {
    const added = Number(axiom.added_count ?? 0);
    const removed = Number(axiom.removed_count ?? 0);
    if (added > 0) push(line(locale, labels.axioms_added, added));
    if (removed > 0) push(line(locale, labels.axioms_removed, removed));
  }

  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">{labels.no_changes}</p>;
  }

  return (
    <div className="space-y-2 text-sm">
      {data.comparison_mode ? (
        <p className="text-xs text-muted-foreground">
          {fmt(labels.mode, { mode: data.comparison_mode })}
          {data.version1 && data.version2
            ? ` · ${data.version1} → ${data.version2}`
            : null}
        </p>
      ) : null}
      <ul className="list-disc space-y-1 pl-5 text-foreground">
        {rows.map((row) => (
          <li key={row}>{row}</li>
        ))}
      </ul>
    </div>
  );
}
