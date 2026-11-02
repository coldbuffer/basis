import type { Locale } from '@/i18n/locale.js';
import { messagesForLocale } from '@/i18n/pick-locale.js';

export function ontologyOwlTypeLabel(locale: Locale, typeUri: string | undefined): string {
  const labels = messagesForLocale(locale).ontology.hub.editor.owl_type_labels as Record<
    string,
    string
  >;
  const key = typeUri?.trim() || 'owl:Class';
  return labels[key] ?? key;
}
