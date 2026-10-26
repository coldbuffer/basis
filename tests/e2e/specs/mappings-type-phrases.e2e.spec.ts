import { expect, test } from '@playwright/test';

import { e2eWorkspaceApiPath } from '../api-v1-path.js';
import { bearerToken, defaultWorkspaceId, registerFreshUser } from '../helpers.js';

test('mappings page shows type relation phrases and deep-links to data quality scan settings', async ({
  page,
}) => {
  test.setTimeout(90_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  const token = await bearerToken(page);

  const getCfg = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'governance/config'), {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(getCfg.ok(), await getCfg.text()).toBeTruthy();
  const cfg = (await getCfg.json()) as {
    config: {
      governor_enabled: boolean;
      governor_interval_minutes: number;
      governor_confidence_min: number;
      governance_ontology_uri?: string | null;
    };
  };

  const put = await page.request.put(e2eWorkspaceApiPath(workspaceId, 'governance/config'), {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: {
      governor_enabled: cfg.config.governor_enabled,
      governor_interval_minutes: cfg.config.governor_interval_minutes,
      governor_confidence_min: cfg.config.governor_confidence_min,
      governance_ontology_uri: cfg.config.governance_ontology_uri ?? '',
      entity_type_surface_phrases: ['e2e_custom_type', '是'],
    },
  });
  expect(put.ok(), await put.text()).toBeTruthy();

  await page.goto(`/workspaces/${workspaceId}/mappings`);
  const banner = page.getByTestId('mappings-type-phrases-banner');
  await expect(banner).toBeVisible({ timeout: 30_000 });
  await expect(banner).toContainText('e2e_custom_type');

  await banner.getByRole('link').click();
  await expect(page).toHaveURL(/\/quality.*tab=scan/, { timeout: 30_000 });
  await expect(page.getByText(/Entity type relation phrases|实体类型关系词/i).first()).toBeVisible({
    timeout: 30_000,
  });
});
