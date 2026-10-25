import { describe, expect, it } from 'vitest';

import { resolveOntologyHubTab } from '@/modules/analyze/lib/hub-tabs.js';

describe('resolveOntologyHubTab', () => {
  it('defaults to registry', () => {
    expect(resolveOntologyHubTab(null, false, false, null)).toBe('registry');
  });

  it('opens editor when entity deep link is present', () => {
    expect(resolveOntologyHubTab(null, false, true, null)).toBe('editor');
  });
});
