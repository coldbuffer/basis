import { describe, expect, it } from 'vitest';
import { messagesForLocale } from '@/i18n/pick-locale.js';
import {
  documentTimelineDiffRange,
  documentTimelineEventLine,
} from '@/modules/workspace/library/lib/document-timeline.js';

describe('documentTimelineEventLine', () => {
  const copy = messagesForLocale('en').library.sources.timeline;

  it('derives diff range from event instants', () => {
    expect(documentTimelineDiffRange([])).toEqual({});
    expect(
      documentTimelineDiffRange([{ kind: 'version_created', at: '2024-01-02T00:00:00Z' }]),
    ).toEqual({ to: '2024-01-02T00:00:00Z' });
    expect(
      documentTimelineDiffRange([
        { kind: 'version_created', at: '2024-01-03T00:00:00Z' },
        { kind: 'processing_job', at: '2024-01-01T00:00:00Z' },
      ]),
    ).toEqual({ from: '2024-01-01T00:00:00Z', to: '2024-01-03T00:00:00Z' });
  });

  it('formats processing job with optional error code', () => {
    const line = documentTimelineEventLine(copy, {
      kind: 'processing_job',
      status: 'failed',
      error_code: 'processing_failed',
    });
    expect(line).toContain('failed');
    expect(line).toContain('processing_failed');
  });
});
