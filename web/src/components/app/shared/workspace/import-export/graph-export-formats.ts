/** Formats accepted by `POST .../export` (semantica `export_graph`). */

export type GraphExportFormat =
  | 'json'
  | 'csv'
  | 'ttl'
  | 'ntriples'
  | 'jsonld'
  | 'rdfxml'
  | 'graphml';

export type GraphExportFormatMeta = {
  format: GraphExportFormat;
  /** File extension for download (matches Content-Disposition from API). */
  extension: string;
  /** `kbImportExport` key describing payload contents. */
  includedKey:
    | 'included_json'
    | 'included_csv'
    | 'included_rdf'
    | 'included_graphml';
};

export const GRAPH_EXPORT_FORMATS: GraphExportFormatMeta[] = [
  { format: 'json', extension: 'json', includedKey: 'included_json' },
  { format: 'csv', extension: 'csv', includedKey: 'included_csv' },
  { format: 'ttl', extension: 'ttl', includedKey: 'included_rdf' },
  { format: 'ntriples', extension: 'nt', includedKey: 'included_rdf' },
  { format: 'jsonld', extension: 'jsonld', includedKey: 'included_rdf' },
  { format: 'rdfxml', extension: 'rdf', includedKey: 'included_rdf' },
  { format: 'graphml', extension: 'graphml', includedKey: 'included_graphml' },
];

export function graphExportExtension(format: GraphExportFormat): string {
  return GRAPH_EXPORT_FORMATS.find((row) => row.format === format)?.extension ?? format;
}
