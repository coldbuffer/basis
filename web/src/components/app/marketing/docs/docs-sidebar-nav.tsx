import { Link, useLocation } from 'react-router-dom';

import { useI18n } from '@/i18n/context.js';
import { productDocsPageTree } from '@/modules/public/docs/lib/product-docs-source.js';
import { cn } from '@/lib/utils.js';

import type { Node, Separator as SeparatorNode } from 'fumadocs-core/page-tree';

function isSeparator(node: Node): node is SeparatorNode {
  return node.type === 'separator';
}

function DocsSidebarNodes({ nodes }: { nodes: Node[] }) {
  const { pathname } = useLocation();

  return (
    <div className="space-y-0.5">
      {nodes.map((node, index) => {
        if (isSeparator(node)) {
          if (!node.name) return null;
          return (
            <p
              key={`sep-${index}-${String(node.name)}`}
              className="px-2 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground first:pt-0"
            >
              {node.name}
            </p>
          );
        }

        if (node.type === 'folder') {
          return (
            <div key={node.$id ?? `folder-${index}`} className="space-y-0.5">
              {node.name ? (
                <p className="px-2 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground first:pt-0">
                  {node.name}
                </p>
              ) : null}
              <DocsSidebarNodes nodes={node.children} />
            </div>
          );
        }

        if (node.type !== 'page') return null;

        const href = node.url;
        const active = pathname === href || (href !== '/docs' && pathname.startsWith(`${href}/`));

        return (
          <Link
            key={node.url}
            to={href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'block rounded-md px-2 py-1.5 text-[13px] leading-5 transition-colors',
              active
                ? 'bg-accent font-medium text-foreground'
                : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
            )}
          >
            {node.name}
          </Link>
        );
      })}
    </div>
  );
}

type DocsSidebarNavProps = {
  className?: string;
};

export function DocsSidebarNav({ className }: DocsSidebarNavProps) {
  const { t, locale } = useI18n();
  const tree = productDocsPageTree(locale);

  return (
    <nav aria-label={t.docs.page.sidebar_aria} className={className} data-testid="docs-sidebar">
      <DocsSidebarNodes nodes={tree.children} />
    </nav>
  );
}

/** Flat page list for mobile `<Select>` (order from meta.json). */
export function useProductDocsFlatPages() {
  const { locale } = useI18n();
  const tree = productDocsPageTree(locale);
  const items: { url: string; name: string }[] = [];

  const walk = (nodes: Node[]) => {
    for (const node of nodes) {
      if (node.type === 'page') {
        items.push({ url: node.url, name: String(node.name ?? node.url) });
      } else if (node.type === 'folder') {
        walk(node.children);
      }
    }
  };
  walk(tree.children);
  return items;
}
