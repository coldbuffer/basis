import { Button } from '@/components/ui/button.js';
import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import type { LocaleMessages } from '@/i18n/en.js';
import type {
  OntologyAxiomChange,
  OntologyEditorDraftDiff,
  OntologyRestrictionChange,
} from '../lib/ontology-editor-draft.js';
import {
  ONTOLOGY_RESTRICTION_OPTIONS,
  parseRestrictionOptionValue,
  restrictionMetaForChange,
  restrictionOptionValue,
} from '../lib/ontology-restriction-types.js';

type EditorCopy = LocaleMessages['ontology']['hub']['editor'];

type OntologyEditorDraftPanelProps = {
  copy: EditorCopy;
  draftDiff: OntologyEditorDraftDiff;
  onChange: (next: OntologyEditorDraftDiff) => void;
};

export function OntologyEditorDraftPanel({ copy, draftDiff, onChange }: OntologyEditorDraftPanelProps) {
  const hasPending =
    draftDiff.added_axioms.length > 0 ||
    draftDiff.added_restrictions.length > 0 ||
    draftDiff.added_edges.length > 0;

  if (!hasPending) return null;

  const restrictionTypeLabels = copy.restriction_types;

  const updateAxiom = (index: number, patch: Partial<OntologyAxiomChange>) => {
    const next = [...draftDiff.added_axioms];
    next[index] = { ...next[index], ...patch };
    onChange({ ...draftDiff, added_axioms: next });
  };

  const removeAxiom = (index: number) => {
    onChange({
      ...draftDiff,
      added_axioms: draftDiff.added_axioms.filter((_, i) => i !== index),
    });
  };

  const updateRestriction = (index: number, patch: Partial<OntologyRestrictionChange>) => {
    const next = [...draftDiff.added_restrictions];
    next[index] = { ...next[index], ...patch };
    onChange({ ...draftDiff, added_restrictions: next });
  };

  const removeRestriction = (index: number) => {
    onChange({
      ...draftDiff,
      added_restrictions: draftDiff.added_restrictions.filter((_, i) => i !== index),
    });
  };

  return (
    <section className="mt-6 border-t border-border pt-4">
      <h4 className="mb-3 text-sm font-semibold text-foreground">{copy.pending_changes_title}</h4>
      {draftDiff.added_edges.length > 0 ? (
        <div className="mb-4">
          <Label className="text-xs text-muted-foreground">{copy.pending_edges_label}</Label>
          <ul className="mt-1 space-y-1 text-xs text-muted-foreground">
            {draftDiff.added_edges.map((edge) => (
              <li key={`${edge.source}-${edge.type}-${edge.target}`} className="font-mono break-all">
                {edge.source} —{edge.type}→ {edge.target}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {draftDiff.added_axioms.map((axiom, index) => (
        <div key={`axiom-${index}`} className="mb-3 space-y-2 rounded-md border border-border p-3">
          <div className="flex items-center justify-between gap-2">
            <Label className="text-xs">{copy.axiom_row_label}</Label>
            <Button type="button" variant="ghost" size="sm" className="h-7 px-2" onClick={() => removeAxiom(index)}>
              <PublicIcon name="trash-01" size={14} />
            </Button>
          </div>
          <NativeSelect
            value={axiom.type}
            onChange={(event) => updateAxiom(index, { type: event.target.value })}
            className="text-xs"
            size="sm"
          >
            <NativeSelectOption value="subClassOf">{copy.axiom_type_subclass}</NativeSelectOption>
          </NativeSelect>
          <Input
            className="h-8 font-mono text-xs"
            placeholder={copy.axiom_subject_placeholder}
            value={axiom.subject ?? ''}
            onChange={(event) => updateAxiom(index, { subject: event.target.value })}
          />
          <Input
            className="h-8 font-mono text-xs"
            placeholder={copy.axiom_object_placeholder}
            value={axiom.object ?? axiom.value ?? ''}
            onChange={(event) => updateAxiom(index, { object: event.target.value })}
          />
        </div>
      ))}
      {draftDiff.added_restrictions.map((restriction, index) => {
        const scope = restriction.property_scope === 'data' ? 'data' : 'object';
        const selectValue = restrictionOptionValue(scope, restriction.type);
        const meta = restrictionMetaForChange(restriction);
        return (
          <div key={`restriction-${index}`} className="mb-3 space-y-2 rounded-md border border-border p-3">
            <div className="flex items-center justify-between gap-2">
              <Label className="text-xs">{copy.restriction_row_label}</Label>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2"
                onClick={() => removeRestriction(index)}
              >
                <PublicIcon name="trash-01" size={14} />
              </Button>
            </div>
            <NativeSelect
              value={selectValue}
              onChange={(event) => {
                const parsed = parseRestrictionOptionValue(event.target.value);
                if (!parsed) return;
                updateRestriction(index, {
                  property_scope: parsed.scope,
                  type: parsed.type,
                });
              }}
              className="text-xs"
              size="sm"
            >
              {ONTOLOGY_RESTRICTION_OPTIONS.map((option) => (
                <NativeSelectOption key={option.value} value={option.value}>
                  {restrictionTypeLabels[option.labelKey]}
                </NativeSelectOption>
              ))}
            </NativeSelect>
            <Input
              className="h-8 font-mono text-xs"
              placeholder={copy.restriction_class_uri_placeholder}
              value={restriction.class_uri ?? ''}
              onChange={(event) => updateRestriction(index, { class_uri: event.target.value })}
            />
            <Input
              className="h-8 font-mono text-xs"
              placeholder={copy.restriction_property_placeholder}
              value={restriction.onProperty ?? ''}
              onChange={(event) => updateRestriction(index, { onProperty: event.target.value })}
            />
            {meta?.needsCardinality ? (
              <Input
                className="h-8 font-mono text-xs"
                type="number"
                min={0}
                step={1}
                placeholder={copy.restriction_cardinality_placeholder}
                value={restriction.cardinality ?? ''}
                onChange={(event) => {
                  const raw = event.target.value;
                  updateRestriction(index, {
                    cardinality: raw === '' ? undefined : Number.parseInt(raw, 10),
                  });
                }}
              />
            ) : null}
            {meta?.needsClassFiller ? (
              <Input
                className="h-8 font-mono text-xs"
                placeholder={copy.restriction_class_placeholder}
                value={restriction.filler_class ?? restriction.onClass ?? ''}
                onChange={(event) => updateRestriction(index, { filler_class: event.target.value })}
              />
            ) : null}
            {meta?.needsIndividualFiller ? (
              <Input
                className="h-8 font-mono text-xs"
                placeholder={copy.restriction_individual_placeholder}
                value={restriction.filler_individual ?? ''}
                onChange={(event) => updateRestriction(index, { filler_individual: event.target.value })}
              />
            ) : null}
            {meta?.needsDatatypeFiller ? (
              <Input
                className="h-8 font-mono text-xs"
                placeholder={copy.restriction_datatype_placeholder}
                value={restriction.filler_datatype ?? ''}
                onChange={(event) => updateRestriction(index, { filler_datatype: event.target.value })}
              />
            ) : null}
            {meta?.needsLiteralValue ? (
              <Input
                className="h-8 font-mono text-xs"
                placeholder={copy.restriction_literal_placeholder}
                value={restriction.literal_value ?? ''}
                onChange={(event) => updateRestriction(index, { literal_value: event.target.value })}
              />
            ) : null}
          </div>
        );
      })}
    </section>
  );
}
