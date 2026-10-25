import { expect, test, type Page } from '@playwright/test';

import { ensurePlatformAdminSession, gotoPlatformAdminPath } from '../e2e-admin-session.js';

test('platform users page lists the registering admin', async ({ page }) => {
  test.setTimeout(90_000);

  const { email } = await ensurePlatformAdminSession(page);
  await gotoPlatformAdminPath(page, '/admin/users');

  await expect(page.getByRole('button', { name: /Create user|创建用户/i })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByText(email)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('E2E User').first()).toBeVisible();
});

test('platform workspaces page shows catalog table and create action', async ({ page }) => {
  test.setTimeout(90_000);

  await ensurePlatformAdminSession(page);
  await gotoPlatformAdminPath(page, '/admin/workspaces');

  await expect(page).toHaveURL(/\/admin\/workspaces/);
  await expect(page.getByRole('columnheader', { name: /Name|名称/i })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByRole('button', { name: /New workspace|新建工作区/i })).toBeVisible({
    timeout: 30_000,
  });
});

test('platform models page shows LLM tab and add provider action', async ({ page }) => {
  test.setTimeout(90_000);

  await ensurePlatformAdminSession(page);
  await gotoPlatformAdminPath(page, '/admin/models');
  await expect(page.getByRole('tab', { name: /^LLM$/ })).toBeVisible({ timeout: 30_000 });
  await expect(
    page.getByRole('button', { name: /Add provider|添加服务商/i }).first(),
  ).toBeVisible({ timeout: 30_000 });
});

test('platform settings page shows access and org SSO sections', async ({ page }) => {
  test.setTimeout(90_000);

  await ensurePlatformAdminSession(page);
  await gotoPlatformAdminPath(page, '/admin/settings');
  await expect(page.getByRole('heading', { name: /^Login$|^登录$/ })).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByRole('heading', { name: /Organization SSO|组织 SSO/i }),
  ).toBeVisible();
});

test('platform audit page shows filters and refresh', async ({ page }) => {
  test.setTimeout(90_000);

  await ensurePlatformAdminSession(page);
  await gotoPlatformAdminPath(page, '/admin/audit');
  await expect(page.getByPlaceholder(/Filter by workspace ID|按工作区 ID 筛选/i)).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole('button', { name: /Refresh|刷新/i })).toBeVisible();
});
