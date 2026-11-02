/**
 * ConceptTree.tsx — react-arborist SKOS hierarchy viewer.
 */
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import React, { useLayoutEffect, useRef, useState } from 'react';
import { Tree } from 'react-arborist';
import type { NodeRendererProps } from 'react-arborist';
import type { ConceptNode } from '../lib/types.js';
import {
  exWsVocabTreeChevron,
  exWsVocabTreeIcon,
  exWsVocabTreeLabel,
  exWsVocabTreeRow,
  exWsVocabTreeShell,
} from '@/lib/ui-classes/ws-ui.js';

interface ConceptTreeProps {
  data: ConceptNode[];
  onSelectConcept: (concept: ConceptNode) => void;
}

function ConceptTreeNode({
  nodeProps,
  onSelectConcept,
}: {
  nodeProps: NodeRendererProps<ConceptNode>;
  onSelectConcept: (concept: ConceptNode) => void;
}) {
  const { node, style: rowPosition, dragHandle } = nodeProps;
  const rowRef = useRef<HTMLDivElement | null>(null);
  const isFolder = node.children && node.children.length > 0;

  useLayoutEffect(() => {
    const el = rowRef.current;
    if (!el) return;
    Object.assign(el.style, rowPosition);
  });

  const setRowRef = (el: HTMLDivElement | null) => {
    rowRef.current = el;
    if (typeof dragHandle === 'function') {
      dragHandle(el);
    }
  };

  return (
    <div
      ref={setRowRef}
      className={exWsVocabTreeRow}
      data-selected={node.isSelected ? 'true' : 'false'}
      onClick={() => {
        node.toggle();
        onSelectConcept(node.data);
      }}
    >
      <span className={exWsVocabTreeChevron}>
        {isFolder ? (
          node.isOpen ? (
            <PublicIcon name='chevron-down' size={14} className="text-muted-foreground" />
          ) : (
            <PublicIcon name='chevron-right' size={14} className="text-muted-foreground" />
          )
        ) : null}
      </span>

      <span className={exWsVocabTreeIcon}>
        {isFolder ? (
          <PublicIcon name='folder' size={14} className="text-primary" />
        ) : (
          <PublicIcon name='file-01' size={14} className="text-muted-foreground" />
        )}
      </span>

      <span className={exWsVocabTreeLabel}>{node.data.pref_label}</span>
    </div>
  );
}

export const ConceptTree: React.FC<ConceptTreeProps> = ({ data, onSelectConcept }) => {
  const shellRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useLayoutEffect(() => {
    const el = shellRef.current;
    if (!el) return;
    const update = () => {
      const rect = el.getBoundingClientRect();
      setSize({
        width: Math.max(0, Math.floor(rect.width)),
        height: Math.max(0, Math.floor(rect.height)),
      });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={shellRef} className={exWsVocabTreeShell}>
      {size.height > 0 ? (
      <Tree
        data={data}
        idAccessor="uri"
        width={size.width}
        height={size.height}
        indent={20}
        rowHeight={32}
        childrenAccessor="children"
      >
        {(nodeProps: NodeRendererProps<ConceptNode>) => (
          <ConceptTreeNode nodeProps={nodeProps} onSelectConcept={onSelectConcept} />
        )}
      </Tree>
      ) : null}
    </div>
  );
};
