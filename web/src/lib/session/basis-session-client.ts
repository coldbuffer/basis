import { createBasisSessionClient } from '@/lib/openapi/transport.js';

import { basisApiBaseUrl } from '@/lib/openapi/basis-api-url.js';
import { getToken } from '@/lib/session/auth-token.js';
import { ensureRequestIdHeader } from '@/lib/workspace/request-id.js';

let _client: ReturnType<typeof createBasisSessionClient> | null = null;
let _clientBaseUrl: string | null = null;

export function basisSessionClient() {
  const baseUrl = basisApiBaseUrl();
  if (!_client || _clientBaseUrl !== baseUrl) {
    _clientBaseUrl = baseUrl;
    _client = createBasisSessionClient({
      baseUrl,
      getAccessToken: getToken,
      beforeRequest: ensureRequestIdHeader,
    });
  }
  return _client;
}
