import { describe, expect, it } from 'vitest';
import {
  processingJobPath,
  processingPath,
  parseProcessingUrlState,
} from '@/modules/workspace/processing/lib/processing-url-state.js';

describe('processingUrlState', () => {
  it('parses job id', () => {
    expect(parseProcessingUrlState('?job=job-9').jobId).toBe('job-9');
  });

  it('parses filter', () => {
    expect(parseProcessingUrlState('?filter=failed').filter).toBe('failed');
  });

  it('builds processing job deep link', () => {
    expect(processingJobPath('kb-1', 'job-9')).toBe('/workspaces/kb-1/processing?job=job-9');
  });

  it('builds processing list with filter', () => {
    expect(processingPath('kb-1', { filter: 'failed' })).toBe(
      '/workspaces/kb-1/processing?filter=failed',
    );
  });
});
