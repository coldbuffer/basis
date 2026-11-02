import type { LocaleMessages } from '@/i18n/en.js';

type Copy = LocaleMessages['graph']['projection'];

export function graphProjectionStatusLabel(copy: Copy, status: string): string {
  const labels = copy.projection_status_labels as Record<string, string>;
  return labels[status] ?? labels[status.toLowerCase()] ?? status;
}
