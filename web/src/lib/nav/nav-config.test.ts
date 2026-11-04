import { describe, expect, it } from 'vitest';

import {
  workspaceOntologyProposalPath,
  platformAdminEntryPath,
  visiblePlatformNavItems,
} from '@/lib/nav/nav-config.js';

describe('visiblePlatformNavItems', () => {
  it('hides cloud-only platform nav in desktop product mode', () => {
    const keys = visiblePlatformNavItems(true, true, true).map((i) => i.labelKey);
    expect(keys).not.toContain('users');
    expect(keys).not.toContain('audit');
    expect(keys).not.toContain('system');
    expect(keys).toContain('models');
  });

  it('desktop admin entry skips hidden system settings', () => {
    expect(platformAdminEntryPath(true, true, true)).toBe('/admin/workspaces');
  });
});

describe('workspaceOntologyProposalPath', () => {
  it('opens ontology versions tab with proposal query', () => {
    expect(workspaceOntologyProposalPath('kb-1', 'prop-42')).toBe(
      '/workspaces/kb-1/ontology?tab=versions&ontologyProposal=prop-42',
    );
  });
});
