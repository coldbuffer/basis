import type { DocSlug } from '@/modules/docs/lib/product-docs-nav.js';
import type { Locale } from '@/i18n/context.js';

/** Strip MDX/Markdown frontmatter and noise for client-side doc search. */
export function plainTextFromDocSource(raw: string, maxLen = 4000): string {
  const body = raw.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '');
  const text = body
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`[^`]+`/g, ' ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/[#>*|_-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return text.length > maxLen ? text.slice(0, maxLen) : text;
}

export function docSlugFromContentFilename(filename: string): DocSlug | null {
  const base = filename.replace(/\.(md|mdx)$/, '');
  if (base === 'index') return 'overview';
  return base as DocSlug;
}

const rawByPath = import.meta.glob('../../../../content/docs/*/*.{md,mdx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** Locale → slug → plain body text (from committed content files). */
export function productDocsBodyTextBySlug(locale: Locale): Partial<Record<DocSlug, string>> {
  const prefix = `../../../../content/docs/${locale}/`;
  const out: Partial<Record<DocSlug, string>> = {};

  for (const [path, raw] of Object.entries(rawByPath)) {
    if (!path.startsWith(prefix)) continue;
    const filename = path.slice(prefix.length);
    const slug = docSlugFromContentFilename(filename);
    if (!slug) continue;
    out[slug] = plainTextFromDocSource(raw);
  }

  return out;
}
