import { Input } from '@/components/ui/input.js';
import { Label } from '@/components/ui/label.js';
import { useI18n } from '@/i18n/context.js';
import type { PlaygroundAuthFieldSpec } from '@/modules/workspace/integration/lib/playground-auth-fields.js';

type Props = {
  fields: PlaygroundAuthFieldSpec[];
  values: Record<string, string>;
  onChange: (key: string, value: string) => void;
  idPrefix: string;
};

/** Integration playground copy of connector auth fields (not shared with `modules/connectors`). */
export function PlaygroundConnectAuthFields({
  fields,
  values,
  onChange,
  idPrefix,
}: Props) {
  const { t } = useI18n();
  const optionalLabel = t.connectors.page.catalog.field_optional;
  return (
    <div className="space-y-3">
      {fields.map((field) => {
        const inputId = `${idPrefix}-${field.key}`;
        const isPassword =
          field.secret || field.input_type === 'password';
        const inputType =
          field.input_type === 'number'
            ? 'number'
            : isPassword
              ? 'password'
              : 'text';
        return (
          <div key={field.key} className="space-y-1">
            <Label htmlFor={inputId}>
              {field.label}
              {field.required === false ? (
                <span className="ml-1 font-normal text-muted-foreground">{optionalLabel}</span>
              ) : null}
            </Label>
            <Input
              id={inputId}
              type={inputType}
              value={values[field.key] ?? ''}
              placeholder={field.placeholder ?? undefined}
              autoComplete="off"
              onChange={(e) => onChange(field.key, e.target.value)}
              data-testid={`integration-playground-auth-field-${idPrefix}-${field.key}`}
            />
            {field.description ? (
              <p className="text-xs text-muted-foreground">{field.description}</p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
