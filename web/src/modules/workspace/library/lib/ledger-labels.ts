import type { LocaleMessages } from '@/i18n/en.js';

type LedgerCopy = LocaleMessages['entities']['ledger'];

export function ledgerStatementStatusLabel(ledger: LedgerCopy, status: string): string {
  const labels = ledger.statement_status_labels as Record<string, string>;
  return labels[status] ?? labels[status.toLowerCase()] ?? status;
}

export function ledgerChunkOriginLabel(ledger: LedgerCopy, origin: string): string {
  const labels = ledger.chunk_origin_labels as Record<string, string>;
  return labels[origin] ?? labels[origin.toLowerCase()] ?? origin;
}
