import { expect, test } from '@playwright/test';

import { e2eWorkspaceApiPath } from '../api-v1-path.js';
import { bearerToken, defaultWorkspaceId, registerFreshUser } from '../helpers';

test('workspace integration page loads (MCP, OpenAPI, access tokens)', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);

  await page.goto(`/workspaces/${workspaceId}/integration`);
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/integration(\\?tab=mcp)?$`), {
    timeout: 60_000,
  });
  await expect(page.getByLabel(/MCP endpoint URL|MCP 端点 URL/i)).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Connect an agent|连接智能体/i)).toBeVisible();

  await page.getByRole('tab', { name: /^OpenAPI$/i }).click();
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/integration\\?tab=openapi`), {
    timeout: 30_000,
  });
  await expect(page.getByTestId('workspace-integration-export-ui-hint')).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId('workspace-integration-alerts-api-hint')).toBeVisible();

  await page.getByRole('tab', { name: /Access tokens|访问令牌/i }).click();
  await expect(page).toHaveURL(new RegExp(`/workspaces/${workspaceId}/integration\\?tab=tokens`), {
    timeout: 30_000,
  });
  await expect(page.getByTestId('integration-tokens-panel')).toBeVisible({ timeout: 30_000 });
});

test('connectors authorization lists end_user connection for subject', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const token = await bearerToken(page);
  const subjectId = 'e2e-playground-subject';

  const put = await page.request.put(
    e2eWorkspaceApiPath(workspaceId, 'connectors/embed/connections/qq_mail'),
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      data: {
        subject_id: subjectId,
        auth_type: 'custom',
        credentials: {
          email: 'e2e@qq.com',
          authorizationCode: 'abcdefghijklmnop',
        },
      },
    },
  );
  expect(put.ok()).toBeTruthy();

  await page.goto(`/workspaces/${workspaceId}/connectors?section=authorization`);
  await expect(page.getByTestId('connectors-catalog-section-authorizations')).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByTestId('configured-connection-qq_mail-end-user')).toBeVisible({
    timeout: 30_000,
  });
});
