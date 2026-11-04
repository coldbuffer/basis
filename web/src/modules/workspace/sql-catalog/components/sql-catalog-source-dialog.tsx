import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Button } from '@/components/ui/button.js';
import { Spinner } from '@/components/ui/spinner.js';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible.js';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.js';
import { Input } from '@/components/ui/input.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { Textarea } from '@/components/ui/textarea.js';
import { useI18n } from '@/i18n/context.js';
import { SqlCatalogEngineIcon } from '@/modules/workspace/sql-catalog/components/sql-catalog-engine-icon.js';

const ENGINES = [
  {
    id: 'postgres',
    schemes: ['postgresql', 'postgres'],
    label: 'PostgreSQL',
    placeholder: 'postgresql://user:password@localhost:5432/dbname',
  },
  {
    id: 'mysql',
    schemes: ['mysql'],
    label: 'MySQL',
    placeholder: 'mysql://user:password@localhost:3306/dbname',
  },
  {
    id: 'sqlite',
    schemes: ['sqlite'],
    label: 'SQLite',
    placeholder: 'sqlite:///absolute/path/database.sqlite',
  },
  {
    id: 'duckdb',
    schemes: ['duckdb'],
    label: 'DuckDB',
    placeholder: 'duckdb:///absolute/path/database.duckdb',
  },
  {
    id: 'clickhouse',
    schemes: ['clickhouse'],
    label: 'ClickHouse',
    placeholder: 'clickhouse://user:password@localhost:8123/dbname',
  },
  {
    id: 'snowflake',
    schemes: ['snowflake'],
    label: 'Snowflake',
    placeholder: 'snowflake://user:password@account?warehouse=WH&database=DB',
  },
  {
    id: 'databricks',
    schemes: ['databricks'],
    label: 'Databricks',
    placeholder: 'databricks://token:dapi@host/catalog?http_path=/sql/1.0/warehouses/id',
  },
  {
    id: 'trino',
    schemes: ['trino'],
    label: 'Trino',
    placeholder: 'trino://user@host:8080/catalog',
  },
  {
    id: 'kyuubi',
    schemes: ['kyuubi'],
    label: 'Kyuubi',
    placeholder: 'kyuubi://user:password@host:10000/catalog',
  },
  {
    id: 'heavydb',
    schemes: ['heavydb'],
    label: 'HeavyDB',
    placeholder: 'heavydb://user:password@localhost:6274/dbname',
  },
] as const;

type EngineId = (typeof ENGINES)[number]['id'];

const SCHEMA_ENGINES = new Set<EngineId>(['databricks', 'snowflake', 'kyuubi', 'trino']);

type DialogMessages = {
  display_name_required: string;
  connection_required: string;
  connection_incomplete: string;
  unsupported_engine: string;
  scheme_mismatch: string;
  invalid_regex: string;
};

export type SqlCatalogSourceDraft = {
  sourceId: string;
  displayName: string;
  connectionUri: string;
  tableDenyRegex: string | null;
  tableAllowRegex: string | null;
  schemas: string[] | null;
};

type FormValues = {
  displayName: string;
  engine: string;
  connectionUri: string;
  tableDenyRegex: string;
  tableAllowRegex: string;
  schemas: string;
};

const emptyValues: FormValues = {
  displayName: '',
  engine: '',
  connectionUri: '',
  tableDenyRegex: '',
  tableAllowRegex: '',
  schemas: '',
};

function schemeOf(uri: string): string | null {
  const match = /^\s*([A-Za-z][A-Za-z0-9+.-]*):/.exec(uri);
  if (!match) return null;
  return match[1].split('+', 1)[0].toLowerCase();
}

function engineForScheme(scheme: string): EngineId | null {
  const found = ENGINES.find((engine) => (engine.schemes as readonly string[]).includes(scheme));
  return found?.id ?? null;
}

function engineById(id: string): (typeof ENGINES)[number] | undefined {
  return ENGINES.find((engine) => engine.id === id);
}

function withScheme(uri: string, scheme: string): string {
  const trimmed = uri.trim();
  if (!trimmed) return '';
  if (/^[A-Za-z][A-Za-z0-9+.-]*:/.test(trimmed)) {
    return trimmed.replace(/^[A-Za-z][A-Za-z0-9+.-]*/, scheme);
  }
  return `${scheme}://${trimmed}`;
}

function hasTarget(uri: string): boolean {
  const body = uri.trim().replace(/^[A-Za-z][A-Za-z0-9+.-]*:(?:\/\/)?/, '');
  return body.replace(/^\/+/, '').length > 0;
}

function optionalRegex(message: string) {
  return z.string().refine((value) => {
    const trimmed = value.trim();
    if (!trimmed) return true;
    try {
      RegExp(trimmed);
      return true;
    } catch {
      return false;
    }
  }, message);
}

function allocateSourceId(displayName: string): string {
  const slug = displayName
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40);
  const base = /^[a-z][a-z0-9-]*$/.test(slug) ? slug : 'src';
  const suffix = Math.random().toString(36).slice(2, 8);
  return `${base}-${suffix}`;
}

function createSourceSchema(copy: DialogMessages) {
  return z
    .object({
      displayName: z.string().trim().min(1, copy.display_name_required),
      engine: z.string(),
      connectionUri: z.string().trim().min(1, copy.connection_required),
      tableDenyRegex: optionalRegex(copy.invalid_regex),
      tableAllowRegex: optionalRegex(copy.invalid_regex),
      schemas: z.string(),
    })
    .superRefine((values, ctx) => {
      const scheme = schemeOf(values.connectionUri);
      const detected = scheme ? engineForScheme(scheme) : null;
      if (!detected) {
        ctx.addIssue({
          code: 'custom',
          path: ['connectionUri'],
          message: copy.unsupported_engine,
        });
        return;
      }
      if (!hasTarget(values.connectionUri)) {
        ctx.addIssue({
          code: 'custom',
          path: ['connectionUri'],
          message: copy.connection_incomplete,
        });
      }
      if (values.engine && values.engine !== detected) {
        ctx.addIssue({
          code: 'custom',
          path: ['connectionUri'],
          message: copy.scheme_mismatch,
        });
      }
    });
}

function parseSchemas(value: string): string[] | null {
  const items = value
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length > 0 ? items : null;
}

export function SqlCatalogSourceDialog({
  open,
  busy,
  onOpenChange,
  onTest,
  onSubmit,
}: {
  open: boolean;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onTest: (connectionUri: string) => Promise<void>;
  onSubmit: (draft: SqlCatalogSourceDraft) => Promise<void>;
}) {
  const { t } = useI18n();
  const copy = t.sql_catalog.dialog;
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testedUri, setTestedUri] = useState<string | null>(null);
  const form = useForm<FormValues>({
    resolver: zodResolver(createSourceSchema(copy)),
    defaultValues: emptyValues,
  });
  const engineId = form.watch('engine');
  const watchedUri = form.watch('connectionUri');
  const selected = engineById(engineId);
  const schemaEngine = selected ? SCHEMA_ENGINES.has(selected.id) : false;
  const connectionReady = testedUri !== null && testedUri === watchedUri.trim();

  useEffect(() => {
    if (!open) return;
    form.reset(emptyValues);
    setFiltersOpen(false);
    setTesting(false);
    setTestedUri(null);
  }, [form, open]);

  function onEngineChange(next: string) {
    const engine = engineById(next);
    if (!engine) return;
    form.setValue('engine', engine.id, { shouldDirty: true });
    const uri = form.getValues('connectionUri');
    const current = schemeOf(uri);
    const currentEngine = current ? engineForScheme(current) : null;
    if (!uri.trim() || currentEngine === engine.id) return;
    form.setValue('connectionUri', withScheme(uri, engine.schemes[0]), {
      shouldValidate: form.formState.isSubmitted,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-h-[min(90vh,44rem)] overflow-y-auto sm:max-w-xl"
        data-testid="sql-catalog-dialog"
      >
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>{copy.description}</DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            className="space-y-4"
            onSubmit={form.handleSubmit(async (values) => {
              const connectionUri = values.connectionUri.trim();
              if (testedUri !== connectionUri) {
                setTesting(true);
                try {
                  await onTest(connectionUri);
                  setTestedUri(connectionUri);
                } catch {
                  setTestedUri(null);
                } finally {
                  setTesting(false);
                }
                return;
              }
              await onSubmit({
                sourceId: allocateSourceId(values.displayName),
                displayName: values.displayName.trim(),
                connectionUri,
                tableDenyRegex: values.tableDenyRegex.trim() || null,
                tableAllowRegex: values.tableAllowRegex.trim() || null,
                schemas: schemaEngine ? parseSchemas(values.schemas) : null,
              });
            })}
          >
            <FormField
              control={form.control}
              name="displayName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{copy.display_name}</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      placeholder={copy.display_name_placeholder}
                      data-testid="sql-catalog-display-name"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="engine"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{copy.engine}</FormLabel>
                  <Select value={field.value || undefined} onValueChange={onEngineChange}>
                    <FormControl>
                      <SelectTrigger className="w-full" data-testid="sql-catalog-engine">
                        <SelectValue placeholder={copy.engine_placeholder}>
                          {selected ? (
                            <span className="flex items-center gap-2">
                              <SqlCatalogEngineIcon scheme={selected.id} />
                              {selected.label}
                            </span>
                          ) : null}
                        </SelectValue>
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {ENGINES.map((engine) => (
                        <SelectItem key={engine.id} value={engine.id}>
                          <span className="flex items-center gap-2">
                            <SqlCatalogEngineIcon scheme={engine.id} />
                            {engine.label}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="connectionUri"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{copy.connection_uri}</FormLabel>
                  <FormControl>
                    <Textarea
                      {...field}
                      rows={3}
                      autoComplete="off"
                      spellCheck={false}
                      placeholder={selected?.placeholder ?? copy.connection_placeholder}
                      className="font-mono text-xs"
                      data-testid="sql-catalog-connection-uri"
                      onChange={(event) => {
                        field.onChange(event.target.value);
                        const detected = engineForScheme(schemeOf(event.target.value) ?? '');
                        if (detected) form.setValue('engine', detected, { shouldDirty: true });
                      }}
                    />
                  </FormControl>
                  <FormDescription className="text-xs">{copy.connection_hint}</FormDescription>
                  {connectionReady ? (
                    <div
                      role="status"
                      data-testid="sql-catalog-test-ok"
                      className="flex items-center gap-2 rounded-md bg-ok-soft px-3 py-2 text-sm text-ok"
                    >
                      <PublicIcon name="check-circle" size={16} />
                      {copy.test_ok}
                    </div>
                  ) : null}
                  <FormMessage />
                </FormItem>
              )}
            />
            <Collapsible open={filtersOpen} onOpenChange={setFiltersOpen}>
              <CollapsibleTrigger asChild>
                <Button type="button" variant="ghost" size="sm" className="h-8 gap-1.5 px-2 text-xs">
                  <PublicIcon name="settings" size={14} />
                  {copy.filters}
                  <PublicIcon
                    name="chevron-down"
                    size={14}
                    className={filtersOpen ? 'rotate-180 transition-transform' : 'transition-transform'}
                  />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-3 pt-3">
                <p className="text-xs text-muted-foreground">{copy.filters_hint}</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <FormField
                    control={form.control}
                    name="tableDenyRegex"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{copy.deny}</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            spellCheck={false}
                            placeholder={copy.deny_placeholder}
                            className="font-mono text-xs"
                            data-testid="sql-catalog-deny"
                          />
                        </FormControl>
                        <FormDescription className="text-xs">{copy.deny_hint}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="tableAllowRegex"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{copy.allow}</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            spellCheck={false}
                            placeholder={copy.allow_placeholder}
                            className="font-mono text-xs"
                            data-testid="sql-catalog-allow"
                          />
                        </FormControl>
                        <FormDescription className="text-xs">{copy.allow_hint}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
                {schemaEngine ? (
                  <FormField
                    control={form.control}
                    name="schemas"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>{copy.schemas}</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            spellCheck={false}
                            placeholder={copy.schemas_placeholder}
                            className="font-mono text-xs"
                            data-testid="sql-catalog-schemas"
                          />
                        </FormControl>
                        <FormDescription className="text-xs">{copy.schemas_hint}</FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                ) : null}
              </CollapsibleContent>
            </Collapsible>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                {copy.cancel}
              </Button>
              <Button type="submit" data-testid="sql-catalog-save" disabled={busy || testing}>
                {testing || busy ? <Spinner /> : null}
                {testing ? copy.testing : busy ? copy.saving : connectionReady ? copy.save : copy.test}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
