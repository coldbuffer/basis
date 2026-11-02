import { describe, expect, it } from "vitest";
import { parseGraphRealtimeServerMessage } from "./graph-realtime-messages.js";

describe("parseGraphRealtimeServerMessage", () => {
  it("maps Basis projection_updated (ingest/rebuild)", () => {
    expect(
      parseGraphRealtimeServerMessage({
        type: "projection_updated",
        workspace_id: "kb-1",
        projection_revision: 4,
      }),
    ).toEqual({
      type: "projection_updated",
      projectionRevision: 4,
    });
  });

  it("maps connected handshake revision", () => {
    expect(
      parseGraphRealtimeServerMessage({
        type: "connected",
        workspace_id: "kb-1",
        projection_revision: 2,
      }),
    ).toEqual({
      type: "connected",
      projectionRevision: 2,
    });
  });

  it("maps access_revoked", () => {
    expect(
      parseGraphRealtimeServerMessage({ type: "access_revoked", workspace_id: "kb-1" }),
    ).toEqual({ type: "access_revoked" });
  });

  it("maps semantica graph_mutation envelope", () => {
    expect(
      parseGraphRealtimeServerMessage({
        event: "graph_mutation",
        data: {
          event_type: "ADD_NODE",
          payload: { id: "n1", label: "A" },
        },
      }),
    ).toEqual({
      type: "graph_mutation",
      eventType: "ADD_NODE",
      payload: { id: "n1", label: "A" },
    });
  });
});
