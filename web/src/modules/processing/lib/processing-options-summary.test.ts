import { describe, expect, it } from 'vitest';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import { processingOptionsSummaryLines } from '@/modules/processing/lib/processing-options-summary.js';

describe('processingOptionsSummaryLines', () => {
  const copy = messagesForLocale('en').processing.jobs;

  it('summarizes chunk and extract flags', () => {
    const lines = processingOptionsSummaryLines(
      {
        chunk: true,
        chunk_method: 'recursive',
        chunk_size: 512,
        extract: true,
        ner_method: 'llm',
      },
      copy,
    );
    expect(lines.length).toBeGreaterThanOrEqual(2);
    expect(lines.some((l) => l.includes('recursive'))).toBe(true);
  });
});
