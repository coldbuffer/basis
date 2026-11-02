/** OWL 2 class restriction kinds (object + data property), aligned with hub `restriction_types.py`. */

export type OntologyPropertyScope = 'object' | 'data';

export type OntologyRestrictionTypeKey =
  | 'someValuesFrom'
  | 'allValuesFrom'
  | 'hasValue'
  | 'minQualifiedCardinality'
  | 'maxQualifiedCardinality'
  | 'qualifiedCardinality'
  | 'minCardinality'
  | 'maxCardinality'
  | 'cardinality';

export type OntologyRestrictionOption = {
  scope: OntologyPropertyScope;
  type: OntologyRestrictionTypeKey;
  /** Stable value for `<select>` (`object:someValuesFrom`). */
  value: string;
  /** i18n key under `ontology.hub.editor.restriction_types.*`. */
  labelKey: keyof typeof RESTRICTION_TYPE_LABEL_KEYS;
  needsClassFiller: boolean;
  needsIndividualFiller: boolean;
  needsDatatypeFiller: boolean;
  needsLiteralValue: boolean;
  needsCardinality: boolean;
};

const RESTRICTION_TYPE_LABEL_KEYS = {
  object_some_values: 'object_some_values',
  object_all_values: 'object_all_values',
  object_has_value: 'object_has_value',
  object_min_qualified_cardinality: 'object_min_qualified_cardinality',
  object_max_qualified_cardinality: 'object_max_qualified_cardinality',
  object_qualified_cardinality: 'object_qualified_cardinality',
  object_min_cardinality: 'object_min_cardinality',
  object_max_cardinality: 'object_max_cardinality',
  object_cardinality: 'object_cardinality',
  data_some_values: 'data_some_values',
  data_all_values: 'data_all_values',
  data_has_value: 'data_has_value',
  data_min_qualified_cardinality: 'data_min_qualified_cardinality',
  data_max_qualified_cardinality: 'data_max_qualified_cardinality',
  data_qualified_cardinality: 'data_qualified_cardinality',
  data_min_cardinality: 'data_min_cardinality',
  data_max_cardinality: 'data_max_cardinality',
  data_cardinality: 'data_cardinality',
} as const;

function option(
  scope: OntologyPropertyScope,
  type: OntologyRestrictionTypeKey,
  labelKey: keyof typeof RESTRICTION_TYPE_LABEL_KEYS,
  fields: Omit<
    OntologyRestrictionOption,
    'scope' | 'type' | 'value' | 'labelKey'
  >,
): OntologyRestrictionOption {
  return {
    scope,
    type,
    value: `${scope}:${type}`,
    labelKey,
    ...fields,
  };
}

export const ONTOLOGY_RESTRICTION_OPTIONS: OntologyRestrictionOption[] = [
  option('object', 'someValuesFrom', 'object_some_values', {
    needsClassFiller: true,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: false,
  }),
  option('object', 'allValuesFrom', 'object_all_values', {
    needsClassFiller: true,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: false,
  }),
  option('object', 'hasValue', 'object_has_value', {
    needsClassFiller: false,
    needsIndividualFiller: true,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: false,
  }),
  option('object', 'minQualifiedCardinality', 'object_min_qualified_cardinality', {
    needsClassFiller: true,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('object', 'maxQualifiedCardinality', 'object_max_qualified_cardinality', {
    needsClassFiller: true,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('object', 'qualifiedCardinality', 'object_qualified_cardinality', {
    needsClassFiller: true,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('object', 'minCardinality', 'object_min_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('object', 'maxCardinality', 'object_max_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('object', 'cardinality', 'object_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('data', 'someValuesFrom', 'data_some_values', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: true,
    needsLiteralValue: false,
    needsCardinality: false,
  }),
  option('data', 'allValuesFrom', 'data_all_values', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: true,
    needsLiteralValue: false,
    needsCardinality: false,
  }),
  option('data', 'hasValue', 'data_has_value', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: true,
    needsLiteralValue: true,
    needsCardinality: false,
  }),
  option('data', 'minQualifiedCardinality', 'data_min_qualified_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: true,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('data', 'maxQualifiedCardinality', 'data_max_qualified_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: true,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('data', 'qualifiedCardinality', 'data_qualified_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: true,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('data', 'minCardinality', 'data_min_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('data', 'maxCardinality', 'data_max_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
  option('data', 'cardinality', 'data_cardinality', {
    needsClassFiller: false,
    needsIndividualFiller: false,
    needsDatatypeFiller: false,
    needsLiteralValue: false,
    needsCardinality: true,
  }),
];

export function restrictionOptionValue(scope: OntologyPropertyScope, type: string): string {
  return `${scope}:${type}`;
}

export function parseRestrictionOptionValue(value: string): {
  scope: OntologyPropertyScope;
  type: OntologyRestrictionTypeKey;
} | null {
  const [scope, type] = value.split(':') as [OntologyPropertyScope, OntologyRestrictionTypeKey];
  if (scope !== 'object' && scope !== 'data') return null;
  const found = ONTOLOGY_RESTRICTION_OPTIONS.find((o) => o.scope === scope && o.type === type);
  return found ? { scope, type } : null;
}

export function restrictionMetaForChange(
  restriction: { property_scope?: string; type: string },
): OntologyRestrictionOption | undefined {
  const scope = (restriction.property_scope === 'data' ? 'data' : 'object') as OntologyPropertyScope;
  return ONTOLOGY_RESTRICTION_OPTIONS.find((o) => o.scope === scope && o.type === restriction.type);
}
