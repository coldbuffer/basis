import { describe, expect, it } from 'vitest';

import { graphExportExtension, GRAPH_EXPORT_FORMATS } from './graph-export-formats.js';

describe('graphExportFormats', () => {
  it('maps API format ids to download extensions', () => {
    expect(graphExportExtension('ttl')).toBe('ttl');
    expect(graphExportExtension('ntriples')).toBe('nt');
    expect(graphExportExtension('rdfxml')).toBe('rdf');
  });

  it('lists RDF and graph interchange formats', () => {
    const ids = GRAPH_EXPORT_FORMATS.map((row) => row.format);
    expect(ids).toContain('jsonld');
    expect(ids).toContain('graphml');
  });
});
