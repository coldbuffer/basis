/** Parsed server envelopes from workspace graph WebSocket updates (Basis realtime hub). */

export type GraphRealtimeServerMessage =
  | { type: "projection_updated"; projectionRevision?: number }
  | { type: "access_revoked" }
  | { type: "connected"; projectionRevision?: number }
  | { type: "connection_ack" }
  | {
      type: "graph_mutation";
      eventType: string;
      payload: Record<string, unknown> | undefined;
    }
  | { type: "unknown" };

function readProjectionRevision(message: Record<string, unknown>): number | undefined {
  return typeof message.projection_revision === "number"
    ? message.projection_revision
    : undefined;
}

export function parseGraphRealtimeServerMessage(raw: unknown): GraphRealtimeServerMessage {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return { type: "unknown" };
  }
  const message = raw as Record<string, unknown>;

  if (message.type === "projection_updated") {
    return {
      type: "projection_updated",
      projectionRevision: readProjectionRevision(message),
    };
  }
  if (message.type === "access_revoked") {
    return { type: "access_revoked" };
  }
  if (message.type === "connected") {
    return {
      type: "connected",
      projectionRevision: readProjectionRevision(message),
    };
  }
  if (message.event === "connection_ack") {
    return { type: "connection_ack" };
  }
  if (message.event === "graph_mutation") {
    const data = message.data;
    const eventType =
      data && typeof data === "object" && !Array.isArray(data)
        ? String((data as { event_type?: unknown }).event_type ?? "")
        : "";
    const payload =
      data && typeof data === "object" && !Array.isArray(data)
        ? ((data as { payload?: unknown }).payload as Record<string, unknown> | undefined)
        : undefined;
    return { type: "graph_mutation", eventType, payload };
  }

  return { type: "unknown" };
}
