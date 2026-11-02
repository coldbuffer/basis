const RDF_TYPE_URI = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";

export function isRdfTypePredicate(predicateUri: string): boolean {
  const probe = predicateUri.trim();
  if (!probe) return false;
  if (probe === RDF_TYPE_URI) return true;
  const fragment = probe.includes("#")
    ? probe.split("#").pop()
    : probe.includes("/")
      ? probe.split("/").pop()
      : probe;
  return fragment === "type";
}
