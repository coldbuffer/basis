import { expect, test } from '@playwright/test';

import { e2eWorkspaceApiPath } from '../api-v1-path.js';
import { bearerToken, defaultWorkspaceId, registerFreshUser } from '../helpers.js';

test('mappings page shows type relation phrases and interpretation config dialog', async ({ page }) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const token = await bearerToken(page);

  const put = await page.request.put(e2eWorkspaceApiPath(workspaceId, 'governance/interpretation'), {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { entity_type_surface_phrases: ['e2e_custom_type', '是'] },
  });
  expect(put.ok(), await put.text()).toBeTruthy();

  await page.goto(`/workspaces/${workspaceId}/ontology?tab=statement`);
  const banner = page.getByTestId('mappings-type-phrases-banner');
  await expect(banner).toBeVisible({ timeout: 30_000 });
  await expect(banner).toContainText('e2e_custom_type');

  await banner.getByRole('link').click();
  const panel = page.getByTestId('interpretation-config-panel');
  await expect(panel).toBeVisible({ timeout: 30_000 });
  await expect(panel.getByLabel(/Entity type relation phrases|类型关系词/i)).toHaveValue(
    /e2e_custom_type/,
  );
});
