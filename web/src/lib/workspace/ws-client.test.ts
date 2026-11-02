import { describe, expect, it } from 'vitest';
import { WorkspaceWsClient } from './ws-client.js';

describe('WorkspaceWsClient.path', () => {
  it('resolves workspace-scoped and absolute API paths', () => {
    const client = new WorkspaceWsClient('kb-uuid-123');
    expect(client.path('graph/stats')).toBe('/api/v1/workspaces/kb-uuid-123/graph/stats');
    expect(client.path('/documents')).toBe('/api/v1/workspaces/kb-uuid-123/documents');
    expect(client.path(`graph/nodes/${encodeURIComponent('a/b')}/neighbors`)).toBe(
      '/api/v1/workspaces/kb-uuid-123/graph/nodes/a%2Fb/neighbors',
    );
    expect(client.path('/api/v1/platform')).toBe('/api/v1/platform');
  });
});
