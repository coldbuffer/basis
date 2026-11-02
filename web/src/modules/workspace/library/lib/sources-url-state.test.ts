import { describe, expect, it } from 'vitest';
import {
  sourcesDocumentPath,
  sourcesProcessPath,
  parseSourcesUrlState,
} from '@/modules/workspace/library/lib/sources-url-state.js';

describe('sourcesUrlState', () => {
  it('parses document focus and process dialog flags', () => {
    expect(parseSourcesUrlState('?doc=paper-1').docId).toBe('paper-1');
    expect(parseSourcesUrlState('?version=v-1').openProcessDialog).toBe(false);
    expect(parseSourcesUrlState('?version=v-1&process=1').openProcessDialog).toBe(true);
  });

  it('builds document and process deep links', () => {
    expect(sourcesDocumentPath('kb-1', 'doc-a')).toBe('/workspaces/kb-1/sources?doc=doc-a');
    expect(sourcesProcessPath('kb-1', 'ver-1')).toBe(
      '/workspaces/kb-1/sources?version=ver-1&process=1',
    );
  });
});
