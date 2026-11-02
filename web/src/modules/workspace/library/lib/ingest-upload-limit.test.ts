import { describe, expect, it } from 'vitest';

import { uploadExceedsMaxBytes } from './ingest-upload-limit.js';

describe('uploadExceedsMaxBytes', () => {
  it('returns false when limit is unset', () => {
    const file = new File(['x'], 'a.txt', { type: 'text/plain' });
    expect(uploadExceedsMaxBytes(file, undefined)).toBe(false);
  });

  it('returns true when file is larger than cap', () => {
    const file = new File([new Uint8Array(11)], 'big.bin');
    expect(uploadExceedsMaxBytes(file, 10)).toBe(true);
    expect(uploadExceedsMaxBytes(file, 11)).toBe(false);
  });
});
