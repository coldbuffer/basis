import { expect, test } from '@playwright/test';

import { e2eApiBaseUrl } from '../api-v1-path.js';
import { ensureUserOrganization, registerFreshUser } from '../helpers';

test('org SSO hint and login UI follow auth_policy', async ({ page }) => {
  test.setTimeout(120_000);

  const { email } = await registerFreshUser(page);
  const domain = email.split('@')[1];
  expect(domain).toBeTruthy();

  const token = await page.evaluate(() => localStorage.getItem('basis_token'));
  expect(token).toBeTruthy();

  const api = e2eApiBaseUrl();
  const orgId = await ensureUserOrganization(page);

  async function upsertOidc(authPolicy: string) {
    const put = await page.request.put(`${api}/api/v1/orgs/${orgId}/oidc`, {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        issuer: 'https://idp.example.com/application/o/basis-e2e/',
        client_id: 'e2e-client',
        client_secret: 'e2e-secret',
        scopes: 'openid email profile',
        email_domains: [domain],
        enabled: true,
        auth_policy: authPolicy,
      },
    });
    expect(put.ok(), `oidc upsert failed: ${put.status()} ${await put.text()}`).toBeTruthy();
  }

  await upsertOidc('sso_preferred');

  const hint = await page.request.get(
    `${api}/api/v1/auth/org-sso-hint?email=${encodeURIComponent(email)}`,
  );
  expect(hint.ok()).toBeTruthy();
  const hintBody = (await hint.json()) as { available?: boolean; password_login_allowed?: boolean };
  expect(hintBody.available).toBe(true);
  expect(hintBody.password_login_allowed).toBe(true);

  const orgRes = await page.request.get(`${api}/api/v1/orgs/${orgId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(orgRes.ok()).toBeTruthy();
  const orgSlug = ((await orgRes.json()) as { organization?: { slug?: string } }).organization
    ?.slug;
  expect(orgSlug).toBeTruthy();

  await page.evaluate(() => localStorage.removeItem('basis_token'));
  await page.goto('/?mode=login');
  await expect(
    page.locator(`[data-testid="login-org-sso"][href*="/oidc/${orgSlug}/"]`),
  ).toBeVisible({ timeout: 30_000 });

  const options = await page.request.get(`${api}/api/v1/auth/org-sso-options`);
  expect(options.ok()).toBeTruthy();
  const optionsBody = (await options.json()) as { options?: Array<{ org_slug: string }> };
  expect(optionsBody.options?.length).toBeGreaterThan(0);

  await page.getByLabel(/Email|邮箱/i).fill(email);
  await expect(page.locator('form button[type="submit"]')).toBeVisible();

  await upsertOidc('sso_required');

  const hintRequired = await page.request.get(
    `${api}/api/v1/auth/org-sso-hint?email=${encodeURIComponent(email)}`,
  );
  const requiredBody = (await hintRequired.json()) as { password_login_allowed?: boolean };
  expect(requiredBody.password_login_allowed).toBe(true);

  await page.goto('/?mode=login');
  await expect(
    page.locator(`[data-testid="login-org-sso"][href*="/oidc/${orgSlug}/"]`),
  ).toBeVisible({ timeout: 30_000 });
  await page.getByLabel(/Email|邮箱/i).fill(email);
  await expect(page.locator('form button[type="submit"]')).toBeVisible();

  await upsertOidc('password_allowed');
});
