/** Client-side guard before multipart ingest (F-SRC-08). */
export function uploadExceedsMaxBytes(
  file: File,
  maxBytes: number | undefined,
): boolean {
  return typeof maxBytes === 'number' && maxBytes > 0 && file.size > maxBytes;
}
