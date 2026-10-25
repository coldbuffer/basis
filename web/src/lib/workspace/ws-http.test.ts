import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { workspaceApiRoot } from '@/lib/workspace/api-path.js';

import {
  buildWorkspaceGraphApiPath,
  buildWorkspaceApiPath,
  workspaceFetchJson,
  resolveWorkspaceApiUrl,
  setActiveWorkspaceHttpConfig,
} from './ws-http.js';

const { workspaceOpenApiResponse } = vi.hoisted(() => ({
  workspaceOpenApiResponse: vi.fn(),
}));

vi.mock('@/lib/openapi/client.js', () => ({
  workspaceOpenApiResponse,
}));

const workspaceId = 'kb-test-uuid';
const root = workspaceApiRoot(workspaceId);

describe('ws-http workspace API scoping (§9.6)', () => {

  beforeEach(() => {
    setActiveWorkspaceHttpConfig({ apiRoot: root });
  });

  it('buildWorkspaceGraphApiPath scopes graph routes under the workspace API root', () => {
    expect(buildWorkspaceGraphApiPath('snapshot', workspaceId)).toBe(`${root}/graph/snapshot`);
    expect(buildWorkspaceGraphApiPath('stats', workspaceId)).toBe(`${root}/graph/stats`);
    expect(buildWorkspaceGraphApiPath('search', workspaceId)).toBe(`${root}/graph/search`);
  });

  it('buildWorkspaceApiPath uses apiRoot when workspaceId is omitted', () => {
    expect(buildWorkspaceApiPath('realtime-ticket')).toBe(`${root}/realtime-ticket`);
  });

  it('resolveWorkspaceApiUrl rewrites standalone Explorer /api/graph paths', () => {
    expect(resolveWorkspaceApiUrl('/api/graph/stats')).toBe(`${root}/graph/stats`);
    expect(resolveWorkspaceApiUrl('/api/graph/nodes?limit=200')).toBe(
      `${root}/graph/nodes?limit=200`,
    );
  });

  it('does not double-rewrite already workspace-scoped paths', () => {
    expect(resolveWorkspaceApiUrl('/api/v1/workspaces/other-kb/graph/stats')).toBe(
      '/api/v1/workspaces/other-kb/graph/stats',
    );
  });

  it('rejects legacy /api paths without workspace host context', () => {
    setActiveWorkspaceHttpConfig({});
    expect(() => buildWorkspaceApiPath('graph/stats')).toThrow(/workspace/i);
    expect(() => resolveWorkspaceApiUrl('/api/graph/stats')).toThrow(/workspace/i);
  });
});

describe('workspaceFetchJson', () => {
  beforeEach(() => {
    setActiveWorkspaceHttpConfig({ apiRoot: root });
    workspaceOpenApiResponse.mockReset();
  });

  afterEach(() => {
    setActiveWorkspaceHttpConfig({});
  });

  it('throws coded errors from API detail', async () => {
    workspaceOpenApiResponse.mockResolvedValue(
      new Response(JSON.stringify({ detail: { code: 'not_found', message: 'x' } }), {
        status: 404,
        headers: { 'content-type': 'application/json' },
      }),
    );
    await expect(workspaceFetchJson('/api/graph/stats')).rejects.toMatchObject({
      code: 'not_found',
    });
    expect(workspaceOpenApiResponse).toHaveBeenCalledWith(
      'GET',
      workspaceId,
      'graph/stats',
      expect.objectContaining({ params: undefined }),
    );
  });

  it('returns JSON on success', async () => {
    workspaceOpenApiResponse.mockResolvedValue(
      new Response(JSON.stringify({ node_count: 3 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );
    const data = await workspaceFetchJson<{ node_count: number }>('/api/graph/stats');
    expect(data.node_count).toBe(3);
  });
});
