import { fmt } from '@/i18n/format.js';
import type { LocaleMessages } from '@/i18n/en.js';

type ProcessingCopy = LocaleMessages['processing']['jobs'];

function flag(options: Record<string, unknown>, key: string): boolean {
  return options[key] === true;
}

function stringOpt(options: Record<string, unknown>, key: string): string | null {
  const v = options[key];
  return typeof v === 'string' && v.trim() ? v.trim() : null;
}

function numberOpt(options: Record<string, unknown>, key: string): number | null {
  const v = options[key];
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() && Number.isFinite(Number(v))) return Number(v);
  return null;
}

/** Human-readable processing pipeline flags for job detail (F-SRC-05). */
export function processingOptionsSummaryLines(
  options: Record<string, unknown>,
  copy: ProcessingCopy,
): string[] {
  const lines: string[] = [];
  if (flag(options, 'chunk')) {
    const method = stringOpt(options, 'chunk_method');
    const size = numberOpt(options, 'chunk_size');
    const overlap = numberOpt(options, 'chunk_overlap');
    lines.push(
      fmt(copy.options_chunk_line, {
        method: method ?? copy.options_unset,
        size: size != null ? String(size) : copy.options_unset,
        overlap: overlap != null ? String(overlap) : copy.options_unset,
      }),
    );
  }
  if (flag(options, 'extract')) {
    const ner = stringOpt(options, 'ner_method');
    const nerModel = stringOpt(options, 'ner_model');
    const llm = stringOpt(options, 'llm_model') ?? stringOpt(options, 'model');
    lines.push(
      fmt(copy.options_extract_line, {
        ner: ner ?? copy.options_unset,
        nerModel: nerModel ?? copy.options_unset,
        llm: llm ?? copy.options_unset,
      }),
    );
  }
  if (flag(options, 'extract_relations')) {
    lines.push(copy.options_relations_on);
  }
  if (flag(options, 'embed') || flag(options, 'embedding')) {
    lines.push(copy.options_embed_on);
  }
  const requestId = stringOpt(options, 'request_id');
  if (requestId) {
    lines.push(fmt(copy.options_request_id, { id: requestId }));
  }
  return lines;
}
