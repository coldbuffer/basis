import { beforeEach, describe, expect, it, vi } from 'vitest';

const createBasisSessionClient = vi.fn(() => ({
  openapi: () => ({}),
}));

vi.mock('@/lib/openapi/transport.js', () => ({
  createBasisSessionClient: (opts: unknown) => createBasisSessionClient(opts),
}));

vi.mock('@/lib/openapi/basis-api-url.js', () => ({
  basisApiBaseUrl: vi.fn(() => ''),
}));

vi.mock('@/lib/session/auth-token.js', () => ({
  getToken: () => null,
}));

vi.mock('@/lib/workspace/request-id.js', () => ({
  ensureRequestIdHeader: (headers: Headers) => headers,
}));

describe('basisSessionClient', () => {
  beforeEach(() => {
    vi.resetModules();
    createBasisSessionClient.mockClear();
  });

  it('reuses the client when api base is unchanged', async () => {
    const { basisApiBaseUrl } = await import('@/lib/openapi/basis-api-url.js');
    vi.mocked(basisApiBaseUrl).mockReturnValue('http://127.0.0.1:9000');

    const { basisSessionClient } = await import('@/lib/session/basis-session-client.js');
    basisSessionClient();
    basisSessionClient();

    expect(createBasisSessionClient).toHaveBeenCalledTimes(1);
    expect(createBasisSessionClient).toHaveBeenCalledWith(
      expect.objectContaining({ baseUrl: 'http://127.0.0.1:9000' }),
    );
  });

  it('recreates the client when api base changes', async () => {
    const { basisApiBaseUrl } = await import('@/lib/openapi/basis-api-url.js');
    vi.mocked(basisApiBaseUrl)
      .mockReturnValueOnce('http://127.0.0.1:9000')
      .mockReturnValueOnce('http://127.0.0.1:9001');

    const { basisSessionClient } = await import('@/lib/session/basis-session-client.js');
    basisSessionClient();
    basisSessionClient();

    expect(createBasisSessionClient).toHaveBeenCalledTimes(2);
    expect(createBasisSessionClient).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ baseUrl: 'http://127.0.0.1:9000' }),
    );
    expect(createBasisSessionClient).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ baseUrl: 'http://127.0.0.1:9001' }),
    );
  });
});
