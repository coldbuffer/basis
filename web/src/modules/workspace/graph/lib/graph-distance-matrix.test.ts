import { describe, expect, it } from 'vitest';
import {
  collectDistanceMatrixNodeIds,
  shouldUseServerStructuralDistance,
  structuralDistancesFromMatrixResponse,
  GRAPH_STRUCTURAL_DISTANCE_LOCAL_MAX_NODES,
} from './graph-distance-matrix.js';
import Graph from 'graphology';

describe('graphDistanceMatrix', () => {
  it('switches to server mode above local node budget', () => {
    expect(shouldUseServerStructuralDistance(GRAPH_STRUCTURAL_DISTANCE_LOCAL_MAX_NODES)).toBe(false);
    expect(shouldUseServerStructuralDistance(GRAPH_STRUCTURAL_DISTANCE_LOCAL_MAX_NODES + 1)).toBe(true);
  });

  it('collects anchor-first node ids with cap', () => {
    const g = new Graph();
    g.addNode('a');
    g.addNode('b');
    g.addNode('c');
    expect(collectDistanceMatrixNodeIds(g, 'b', 2)).toEqual(['b', 'a']);
  });

  it('parses hop distances from matrix row', () => {
    const distances = structuralDistancesFromMatrixResponse(
      {
        nodes: ['anchor', 'n1', 'n2'],
        metric: 'hops',
        matrix: [
          [0, 1, 3],
          [2, 0, 1],
          [4, 1, 0],
        ],
      },
      'anchor',
      2,
    );
    expect(distances).toEqual({ anchor: 0, n1: 1 });
  });
});
