/** Human-readable RDF resource titles (IRI local names when labels are bare IRIs). */

export function localNameFromUri(uri: string): string {
  const text = uri.trim();
  if (!text) return text;
  const trimmed = text.replace(/[/#]+$/, "");
  const hash = trimmed.lastIndexOf("#");
  if (hash >= 0) {
    const local = trimmed.slice(hash + 1);
    if (local) return local;
  }
  const slash = trimmed.lastIndexOf("/");
  if (slash >= 0) {
    const local = trimmed.slice(slash + 1);
    if (local) return local;
  }
  return trimmed || text;
}

function looksLikeIri(value: string): boolean {
  const probe = value.trim().toLowerCase();
  return probe.startsWith("http://") || probe.startsWith("https://") || probe.startsWith("urn:");
}

export function humanizeRdfLabel(
  candidate: string | undefined | null,
  resourceUri: string,
): string {
  const text = String(candidate ?? "").trim();
  if (!text) return localNameFromUri(resourceUri);
  if (/\s/.test(text)) return text;
  if (looksLikeIri(text)) return localNameFromUri(text);
  return text;
}
