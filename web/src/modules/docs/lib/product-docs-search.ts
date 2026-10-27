import type { DocSlug } from '@/modules/docs/lib/product-docs-nav.js';

export type DocsSearchEntry = {
  slug: DocSlug;
  url: string;
  title: string;
  description: string;
  /** Plain text from MDX body (search only). */
  bodyText?: string;
};

function normalizeQuery(raw: string): string {
  return raw.trim().toLocaleLowerCase();
}

/** Lightweight title/description match (no full-text index). */
export function searchProductDocs(entries: DocsSearchEntry[], query: string, limit = 12): DocsSearchEntry[] {
  const q = normalizeQuery(query);
  if (!q) return [];

  const scored: { entry: DocsSearchEntry; score: number }[] = [];
  for (const entry of entries) {
    const title = entry.title.toLocaleLowerCase();
    const desc = entry.description.toLocaleLowerCase();
    let score = 0;
    if (title.includes(q)) score += title.startsWith(q) ? 4 : 2;
    if (desc.includes(q)) score += 1;
    if (entry.slug.replace(/-/g, ' ').includes(q)) score += 1;
    const body = entry.bodyText?.toLocaleLowerCase() ?? '';
    if (body.includes(q)) score += 1;
    if (score > 0) scored.push({ entry, score });
  }

  scored.sort((a, b) => b.score - a.score || a.entry.title.localeCompare(b.entry.title));
  return scored.slice(0, limit).map((row) => row.entry);
}
