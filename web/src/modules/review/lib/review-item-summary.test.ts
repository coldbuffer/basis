import { describe, expect, it } from 'vitest';

import en from '@/modules/review/i18n/en.js';
import { reviewItemSummaryLine, reviewKindLabel } from './review-item-summary.js';

describe('reviewItemSummaryLine', () => {
  const copy = en.queue;
  const emptyCell = '—';

  it('labels vocabulary alignment review kind', () => {
    expect(reviewKindLabel('vocabulary_alignment_change', copy)).toBe('Vocabulary alignment');
  });

  it('summarizes vocabulary alignment upsert payload', () => {
    const line = reviewItemSummaryLine(
      {
        id: 'ri-1',
        kind: 'vocabulary_alignment_change',
        payload: {
          action: 'upsert',
          source_uri: 'http://ex/a#A',
          target_uri: 'http://ex/b#B',
          relation: 'skos:exactMatch',
        },
      },
      copy,
      'en',
      {},
      emptyCell,
    );
    expect(line).toContain('http://ex/a#A');
    expect(line).toContain('skos:exactMatch');
  });
});
