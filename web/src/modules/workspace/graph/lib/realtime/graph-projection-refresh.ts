/** Ignore stale or duplicate projection_updated revisions from the realtime channel. */
export function shouldApplyProjectionRevision(
  lastRevision: number | null,
  incoming?: number,
): boolean {
  if (typeof incoming !== "number") {
    return true;
  }
  if (lastRevision !== null && incoming <= lastRevision) {
    return false;
  }
  return true;
}
