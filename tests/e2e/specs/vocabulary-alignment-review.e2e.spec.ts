import { expect, test } from '@playwright/test';

import { e2eWorkspaceApiPath } from '../api-v1-path.js';
import {
  approveReviewItemViaApi,
  bearerToken,
  defaultWorkspaceId,
  registerFreshUser,
  skipIfReviewWorkspaceUnavailable,
  skipUnlessWorkspaceGraphWrite,
} from '../helpers.js';

test('vocabulary alignment review gate publishes after approve', async ({ page }) => {
  test.setTimeout(180_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await skipUnlessWorkspaceGraphWrite(page, workspaceId);

  const token = await bearerToken(page);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  const putCfg = await page.request.put(e2eWorkspaceApiPath(workspaceId, 'governance/config'), {
    headers,
    data: {
      governor_enabled: false,
      governor_interval_minutes: 1440,
      governor_confidence_min: 0.75,
      vocabulary_alignment_requires_review: true,
    },
  });
  expect(putCfg.ok()).toBeTruthy();

  const createdA = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology'), {
    headers,
    data: { name: 'E2E Review Align A', namespace: 'http://example.org/e2e-vreview-a' },
  });
  expect(createdA.ok()).toBeTruthy();

  const createdB = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology'), {
    headers,
    data: { name: 'E2E Review Align B', namespace: 'http://example.org/e2e-vreview-b' },
  });
  expect(createdB.ok()).toBeTruthy();

  const sourceUri = 'http://example.org/e2e-vreview-a#Term';
  const targetUri = 'http://example.org/e2e-vreview-b#Term';

  const proposed = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology/alignments'), {
    headers,
    data: {
      source_uri: sourceUri,
      target_uri: targetUri,
      relation: 'skos:exactMatch',
      confidence: 0.9,
    },
  });
  expect(proposed.ok()).toBeTruthy();
  const proposedBody = (await proposed.json()) as { status?: string; review_item_id?: string };
  expect(proposedBody.status).toBe('proposed');
  const reviewItemId = proposedBody.review_item_id;
  expect(reviewItemId).toBeTruthy();

  const listedBefore = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'ontology/alignments'), {
    headers,
  });
  expect(listedBefore.ok()).toBeTruthy();
  expect((await listedBefore.json()) as unknown[]).toHaveLength(0);

  await page.goto(`/workspaces/${workspaceId}/review?reviewItem=${encodeURIComponent(reviewItemId!)}`);
  await skipIfReviewWorkspaceUnavailable(page);

  const card = page.locator(`#review-item-${reviewItemId}`);
  await expect(card).toBeVisible({ timeout: 60_000 });
  await expect(card.getByText(/Vocabulary alignment|词汇对齐/)).toBeVisible();
  await expect(card.getByTestId(`review-quality-link-${reviewItemId}`)).toBeVisible();
  await card.getByRole('button', { name: /Publish alignment|发布对齐/i }).click();
  await expect(page.getByTestId('review-approve-decision-link')).toBeVisible({ timeout: 30_000 });

  await expect
    .poll(
      async () => {
        const response = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'ontology/alignments'), {
          headers,
        });
        if (!response.ok()) {
          return 0;
        }
        const rows = (await response.json()) as unknown[];
        return rows.length;
      },
      { timeout: 60_000 },
    )
    .toBe(1);
});

test('vocabulary alignment review gate approve via API', async ({ page }) => {
  test.setTimeout(120_000);

  await registerFreshUser(page);
  const workspaceId = await defaultWorkspaceId(page);
  await skipUnlessWorkspaceGraphWrite(page, workspaceId);

  const token = await bearerToken(page);
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  await page.request.put(e2eWorkspaceApiPath(workspaceId, 'governance/config'), {
    headers,
    data: {
      governor_enabled: false,
      governor_interval_minutes: 1440,
      governor_confidence_min: 0.75,
      vocabulary_alignment_requires_review: true,
    },
  });

  const proposed = await page.request.post(e2eWorkspaceApiPath(workspaceId, 'ontology/alignments'), {
    headers,
    data: {
      source_uri: 'http://example.org/e2e-api-a#X',
      target_uri: 'http://example.org/e2e-api-b#Y',
      relation: 'skos:exactMatch',
      confidence: 0.85,
    },
  });
  expect(proposed.ok()).toBeTruthy();
  const reviewItemId = ((await proposed.json()) as { review_item_id?: string }).review_item_id;
  expect(reviewItemId).toBeTruthy();

  await approveReviewItemViaApi(page, workspaceId, reviewItemId!);

  await expect
    .poll(
      async () => {
        const response = await page.request.get(e2eWorkspaceApiPath(workspaceId, 'ontology/alignments'), {
          headers,
        });
        if (!response.ok()) {
          return '';
        }
        const rows = (await response.json()) as Array<{ source_uri?: string }>;
        return rows[0]?.source_uri ?? '';
      },
      { timeout: 60_000 },
    )
    .toBe('http://example.org/e2e-api-a#X');
});
