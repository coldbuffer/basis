import { z } from 'zod';
import {
  connectionIdentityFromOptionKey,
  type StoredConnection,
} from '@/modules/workspace/connectors/lib/connector-connections.js';
import { streamParamsFromFieldMap } from '@/modules/workspace/connectors/lib/connector-stream-params.js';

export type ConnectorColumnMappingInput = {
  column: string;
  kind: 'literal' | 'relation';
  surface_phrase: string;
  predicate_uri: string;
  writable: boolean;
};

export function createConnectorTableMappingFormSchema(messages: {
  invalidJson: string;
  invalidJsonObject: string;
}) {
  return z.object({
  connectionKey: z.string().min(1),
  streamName: z.string().trim().min(1),
  externalTable: z.string().trim().min(1),
  streamParamsAdvanced: z.boolean(),
  streamParamFields: z.record(z.string(), z.string()),
  streamParamsJson: z.string().trim(),
  primaryKeyColumn: z.string().trim().min(1),
  cursorColumn: z.string().optional(),
  labelColumn: z.string().trim().min(1),
  targetClassUri: z.string().trim().min(1),
  columnsSpec: z.string().trim().min(1),
  syncDirection: z.enum(['inbound', 'bidirectional']),
  writebackMode: z.enum(['disabled', 'review', 'auto']),
  syncMode: z.enum(['full_refresh', 'incremental']),
  trackDeletes: z.boolean(),
  // The number input already emits numbers; `z.coerce` would widen `z.input` and break
  // the `zodResolver` ↔ `useForm` generic match.
  pollIntervalMinutes: z.number().int().min(0).max(10080),
  })
    .superRefine((values, ctx) => {
      if (!values.streamParamsAdvanced) {
        return;
      }
      try {
        const parsed = JSON.parse(values.streamParamsJson || '{}') as unknown;
        if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: messages.invalidJsonObject,
            path: ['streamParamsJson'],
          });
        }
      } catch {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: messages.invalidJson,
          path: ['streamParamsJson'],
        });
      }
    });
}

export type ConnectorTableMappingFormValues = z.infer<
  ReturnType<typeof createConnectorTableMappingFormSchema>
>;

export const defaultConnectorTableMappingFormValues: ConnectorTableMappingFormValues = {
  connectionKey: '',
  streamName: 'table_records',
  externalTable: 'public.customers',
  streamParamsAdvanced: false,
  streamParamFields: {},
  streamParamsJson: '{}',
  primaryKeyColumn: 'id',
  cursorColumn: 'updated_at',
  labelColumn: 'name',
  targetClassUri: 'urn:basis:class:Customer',
  columnsSpec: 'tier:writable,arr:readonly',
  syncDirection: 'bidirectional',
  writebackMode: 'review',
  syncMode: 'incremental',
  trackDeletes: false,
  pollIntervalMinutes: 0,
};

export function parseStreamParamsJson(json: string): Record<string, unknown> {
  const parsed = JSON.parse(json) as unknown;
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('invalid_json_object');
  }
  return parsed as Record<string, unknown>;
}

export function columnMappingsFromSpec(spec: string): ConnectorColumnMappingInput[] {
  return spec
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((pair) => {
      const [col, mode] = pair.split(':').map((x) => x.trim());
      const column = col || 'value';
      return {
        column,
        kind: 'literal' as const,
        surface_phrase: `has ${column}`,
        predicate_uri: `urn:basis:prop:${column}`,
        writable: mode === 'writable',
      };
    });
}

export function columnSpecFromMappings(
  mappings: Array<{ column: string; writable?: boolean }>,
): string {
  if (mappings.length === 0) {
    return defaultConnectorTableMappingFormValues.columnsSpec;
  }
  return mappings
    .map((m) => `${m.column}:${m.writable ? 'writable' : 'readonly'}`)
    .join(',');
}

export function resolveStreamParamsFromFormValues(
  values: ConnectorTableMappingFormValues,
): Record<string, unknown> {
  if (values.streamParamsAdvanced) {
    return parseStreamParamsJson(values.streamParamsJson || '{}');
  }
  return streamParamsFromFieldMap(values.streamParamFields ?? {});
}

export function mappingRequestBodyFromFormValues(
  values: ConnectorTableMappingFormValues,
  connections?: StoredConnection[],
) {
  const { service } = connectionIdentityFromOptionKey(values.connectionKey, connections);
  return {
    provider: service,
    stream_name: values.streamName.trim(),
    external_table: values.externalTable.trim(),
    stream_params: resolveStreamParamsFromFormValues(values),
    primary_key_column: values.primaryKeyColumn.trim(),
    cursor_column: values.cursorColumn?.trim() || null,
    label_column: values.labelColumn.trim(),
    target_class_uri: values.targetClassUri.trim(),
    column_mappings: columnMappingsFromSpec(values.columnsSpec),
    sync_direction: values.syncDirection,
    writeback_mode: values.writebackMode,
    sync_mode: values.syncMode,
    track_deletes: values.trackDeletes,
    poll_interval_minutes: values.pollIntervalMinutes,
  };
}
