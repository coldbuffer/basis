import { type ApiErrorWithMeta } from '@/lib/errors/api-error.js';
import { basisAuthRequired } from '@/lib/runtime/basis-runtime.js';
import { markApiDesktopProduct } from '@/lib/runtime/desktop-product-flag.js';
import { getToken, setToken } from '@/lib/session/auth-token.js';
import { basisSessionClient } from '@/lib/session/basis-session-client.js';
import { publicOpenApiPOST } from '@/lib/openapi/client.js';
import { unwrapOpenApi } from '@/lib/openapi/response.js';

export { getToken, setToken } from '@/lib/session/auth-token.js';

export type BasisUser = {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
};

function shouldAttemptDesktopBootstrap(): boolean {
  if (!basisAuthRequired()) return true;
  if (import.meta.env.MODE === 'desktop') return true;
  const flag = import.meta.env.VITE_BASIS_DESKTOP;
  return flag === 'true' || flag === '1';
}

export async function bootstrapDesktopSession(): Promise<BasisUser | null> {
  try {
    const body = (await publicOpenApiPOST('/api/v1/auth/desktop-session', {
      body: {},
    })) as { user: BasisUser; token: string };
    setToken(body.token);
    markApiDesktopProduct();
    return body.user;
  } catch {
    return null;
  }
}

export async function fetchSession(): Promise<BasisUser | null> {
  let token = getToken();
  if (!token && shouldAttemptDesktopBootstrap()) {
    const desktopUser = await bootstrapDesktopSession();
    if (desktopUser) return desktopUser;
    token = getToken();
  }
  if (!token) return null;
  try {
    const body = unwrapOpenApi(
      await basisSessionClient().openapi().GET('/api/v1/auth/me'),
    ) as { user: BasisUser };
    return body.user;
  } catch (err) {
    const status = (err as ApiErrorWithMeta).status;
    if (status === 401 || status === 403) {
      setToken(null);
    }
    return null;
  }
}

export async function login(input: {
  email: string;
  password: string;
}): Promise<{ user: BasisUser; token: string }> {
  const body = (await publicOpenApiPOST('/api/v1/auth/login', {
    body: { email: input.email, password: input.password },
  })) as { user: BasisUser; token: string };
  setToken(body.token);
  return body;
}

export async function register(input: {
  email: string;
  password: string;
  display_name: string;
}): Promise<{ user: BasisUser; token: string }> {
  const body = (await publicOpenApiPOST('/api/v1/auth/register', {
    body: input,
  })) as { user: BasisUser; token: string };
  setToken(body.token);
  return body;
}

export type LogoutResult = { ok?: boolean; saml_logout_url?: string };

export async function logout(): Promise<LogoutResult> {
  try {
    if (getToken()) {
      const body = unwrapOpenApi(
        await basisSessionClient().openapi().POST('/api/v1/auth/logout'),
      ) as LogoutResult;
      setToken(null);
      return body;
    }
  } finally {
    setToken(null);
  }
  return {};
}
