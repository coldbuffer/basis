import { expect, test } from '@playwright/test';

import { applyWorkspaceSessionLogin } from '../e2e-admin-session.js';
import { e2eApiBaseUrl } from '../api-v1-path.js';
import { ensureUserOrganization, registerFreshUser } from '../helpers';

const SAMPLE_CERT = `-----BEGIN CERTIFICATE-----
MIIBkTCB+wIJAKHBfpEWqJzTMA0GCSqGSIb3DQEBCwUAMBQxEjAQBgNVBAMMCWxv
Y2FsaG9zdDAeFw0yNTAxMDEwMDAwMDBaFw00NTAxMDEwMDAwMDBaMBQxEjAQBgNV
BAMMCWxvY2FsaG9zdDBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABDummyCertFor
TestsOnlyNotValid==
-----END CERTIFICATE-----`;

test('settings shows SAML panel after API configure', async ({ page }) => {
  test.setTimeout(120_000);

  const { email, password } = await registerFreshUser(page);
  const domain = email.split('@')[1];
  expect(domain).toBeTruthy();
  const token = await page.evaluate(() => localStorage.getItem('basis_token'));
  expect(token).toBeTruthy();

  const api = e2eApiBaseUrl();
  const orgId = await ensureUserOrganization(page);

  const put = await page.request.put(`${api}/api/v1/orgs/${orgId}/saml`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      idp_entity_id: 'https://idp.example.com/metadata',
      idp_sso_url: 'https://idp.example.com/sso',
      idp_x509_cert: SAMPLE_CERT,
      idp_slo_url: 'https://idp.example.com/slo',
      slo_enabled: true,
      email_domains: [domain],
      enabled: true,
      auth_policy: 'password_allowed',
    },
  });
  expect(put.ok(), `saml upsert failed: ${put.status()} ${await put.text()}`).toBeTruthy();

  const getSaml = await page.request.get(`${api}/api/v1/orgs/${orgId}/saml`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(getSaml.ok()).toBeTruthy();
  const samlBody = (await getSaml.json()) as { slo_url?: string; slo_enabled?: boolean };
  expect(samlBody.slo_enabled).toBe(true);
  expect(samlBody.slo_url).toContain('/api/v1/auth/saml/slo');

  const options = await page.request.get(`${api}/api/v1/auth/org-sso-options`);
  expect(options.ok()).toBeTruthy();
  const samlOpts = ((await options.json()) as { options?: Array<{ protocol?: string }> }).options?.filter(
    (row) => row.protocol === 'saml',
  );
  expect(samlOpts?.length).toBeGreaterThan(0);

  await expect
    .poll(
      async () => {
        const res = await page.request.get(`${api}/api/v1/orgs`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok()) {
          return false;
        }
        const body = (await res.json()) as {
          organizations?: Array<{ my_org_role?: string | null }>;
        };
        return (body.organizations ?? []).some(
          (o) => o.my_org_role === 'owner' || o.my_org_role === 'admin',
        );
      },
      { timeout: 60_000 },
    )
    .toBe(true);

  await applyWorkspaceSessionLogin(page, { email, password });
  await page.goto('/admin/settings', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('tab', { name: /^SAML$/ })).toBeVisible({ timeout: 120_000 });
  await page.getByRole('tab', { name: /^SAML$/ }).click();
  await expect(page.getByTestId('org-saml-panel')).toBeVisible();
  await expect(page.getByTestId('org-saml-panel')).toContainText(/SAML|saml/i);
  await expect(page.getByTestId('org-saml-panel')).toContainText(/saml\/slo/i);
});
