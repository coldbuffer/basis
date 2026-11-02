import type { Locale } from "@/i18n/locale.js";
import { requestFailedStatusMessage } from "@/i18n/format.js";
import { messagesForLocale } from "@/i18n/pick-locale.js";
import type {
  MarkdownEditorError,
  MarkdownResourceRef,
} from "./markdown-editor-state";
import type { ApiErrorWithMeta } from "@/lib/errors/api-error.js";
import {
  workspaceOpenApiGET,
  workspaceOpenApiPUT,
} from "@/lib/openapi/client.js";

export type MarkdownClientOptions = {
  locale?: Locale;
};

function markdownClientMessages(locale: Locale = "en") {
  const messages = messagesForLocale(locale);
  return {
    networkUnreachable:
      messages.graph.canvas.inspector.markdown.network_unreachable,
    requestFailedStatus: (status: number) =>
      requestFailedStatusMessage(locale, status),
  };
}

export interface MarkdownDocument {
  resource: MarkdownResourceRef;
  source: string;
  body: string;
  revision: string;
  editable: boolean;
}

export interface MarkdownApplyResult extends MarkdownDocument {
  changed: boolean;
}

export class MarkdownClientError extends Error implements MarkdownEditorError {
  readonly kind: MarkdownEditorError["kind"];
  readonly code?: string;
  readonly field?: string;
  readonly currentRevision?: string;

  constructor(error: MarkdownEditorError) {
    super(error.message);
    this.name = "MarkdownClientError";
    this.kind = error.kind;
    this.code = error.code;
    this.field = error.field;
    this.currentRevision = error.currentRevision;
    if (error.code) {
      (this as Error & { code?: string }).code = error.code;
    }
  }
}

function resourceSuffix(ref: MarkdownResourceRef): string {
  return `markdown/${ref.kind}/${encodeURIComponent(ref.id)}`;
}

function apiErrorFromUnknown(
  error: unknown,
  locale: Locale,
): MarkdownClientError {
  if (error instanceof MarkdownClientError) return error;
  const meta = error as ApiErrorWithMeta;
  if (typeof meta?.status === "number") {
    const kind: MarkdownEditorError["kind"] =
      meta.status === 422
        ? "validation"
        : meta.status === 409
          ? "conflict"
          : "save";
    const { requestFailedStatus } = markdownClientMessages(locale);
    const fallback = requestFailedStatus(meta.status);
    const message = meta.code ? "" : (meta.message?.trim() || fallback);
    return new MarkdownClientError({
      kind,
      code: meta.code?.trim() || undefined,
      message,
    });
  }
  return new MarkdownClientError({
    kind: "network",
    message: markdownClientMessages(locale).networkUnreachable,
  });
}

export function readMarkdownResource(
  ref: MarkdownResourceRef,
  workspaceId: string,
  options?: MarkdownClientOptions,
): Promise<MarkdownDocument> {
  const locale = options?.locale ?? "en";
  return workspaceOpenApiGET<MarkdownDocument>(workspaceId, resourceSuffix(ref)).catch(
    (error) => {
      throw apiErrorFromUnknown(error, locale);
    },
  );
}

export function applyMarkdownResource(
  ref: MarkdownResourceRef,
  markdown: string,
  expectedRevision: string,
  workspaceId: string,
  options?: MarkdownClientOptions,
): Promise<MarkdownApplyResult> {
  const locale = options?.locale ?? "en";
  return workspaceOpenApiPUT<MarkdownApplyResult>(workspaceId, resourceSuffix(ref), {
    body: {
      markdown,
      expected_revision: expectedRevision,
    },
  }).catch((error) => {
    throw apiErrorFromUnknown(error, locale);
  });
}
