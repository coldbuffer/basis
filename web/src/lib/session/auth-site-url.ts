import { authV1Path } from '@/lib/openapi/api-v1-path.js';

/** Normalize public site URL (no trailing slash). */
export function normalizeSiteUrl(url: string): string {
  return url.trim().replace(/\/+$/, '');
}

export function platformAuthCallbacks(publicBase: string): Record<string, string> | null {
  const base = normalizeSiteUrl(publicBase);
  if (!base) return null;
  return {
    github: `${base}${authV1Path('oauth/github/callback')}`,
    google: `${base}${authV1Path('oauth/google/callback')}`,
    org_oidc: `${base}${authV1Path('oidc/callback')}`,
    org_saml_acs: `${base}${authV1Path('saml/acs')}`,
    org_saml_slo: `${base}${authV1Path('saml/slo')}`,
  };
}

export function orgSsoPublicUrls(
  publicBase: string,
  orgSlug: string,
): { login_url: string; callback_url: string } | null {
  const base = normalizeSiteUrl(publicBase);
  const slug = orgSlug.trim();
  if (!base || !slug) return null;
  return {
    login_url: `${base}${authV1Path(`oidc/${slug}/start`)}`,
    callback_url: `${base}${authV1Path('oidc/callback')}`,
  };
}
