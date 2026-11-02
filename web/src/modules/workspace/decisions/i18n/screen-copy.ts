import type { AnyLocaleMessages } from '@/i18n/pick-locale.js';

type Copy = AnyLocaleMessages['decisions']['page'];

export function decisionCategoryLabel(copy: Copy, category: string): string {
  const labels = copy.category_labels as Record<string, string>;
  return labels[category] ?? labels[category.toLowerCase()] ?? category;
}

export function decisionOutcomeLabel(copy: Copy, outcome: string): string {
  if (!outcome) return copy.outcome_unknown;
  const labels = copy.outcome_labels as Record<string, string>;
  const direct = labels[outcome] ?? labels[outcome.toLowerCase()];
  if (direct) return direct;
  const normalized = outcome.toLowerCase();
  for (const [key, label] of Object.entries(labels)) {
    if (normalized.includes(key)) return label;
  }
  return outcome;
}

export function decisionChainStepTypeLabel(copy: Copy, type: string): string {
  const labels = copy.step_type_labels as Record<string, string>;
  return labels[type] ?? labels[type.toLowerCase()] ?? type;
}

export function decisionChainRelationshipLabel(copy: Copy, relationship: string): string {
  if (!relationship) return copy.chain_arrow;
  const labels = copy.relationship_labels as Record<string, string>;
  return labels[relationship] ?? labels[relationship.toLowerCase()] ?? relationship;
}
