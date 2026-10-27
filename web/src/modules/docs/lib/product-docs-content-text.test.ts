import { describe, expect, it } from 'vitest';

import {
  docSlugFromContentFilename,
  plainTextFromDocSource,
} from '@/modules/docs/lib/product-docs-content-text.js';

describe('product docs content text', () => {
  it('maps index filename to overview slug', () => {
    expect(docSlugFromContentFilename('index.mdx')).toBe('overview');
    expect(docSlugFromContentFilename('quickstart.mdx')).toBe('quickstart');
  });

  it('strips frontmatter and markdown noise', () => {
    const raw = `---
title: Test
---

## Hello

Visit [Quickstart](/docs/quickstart) and \`code\`.

{/* comment */}

\`\`\`ts
const x = 1;
\`\`\`
`;
    const text = plainTextFromDocSource(raw);
    expect(text).toContain('Hello');
    expect(text).toContain('Quickstart');
    expect(text).not.toContain('const x');
    expect(text).not.toContain('comment');
  });
});
