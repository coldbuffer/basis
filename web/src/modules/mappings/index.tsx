import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { workspaceOntologyHubPath } from '@/modules/analyze/lib/hub-route.js';
import { DataTable, type DataTableColumn } from '@/components/app/shared/console/DataTable.js';
import { Badge } from '@/components/ui/badge.js';
import { Button } from '@/components/ui/button.js';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
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
import { useI18n } from '@/i18n/context.js';
import { formatLocaleDateTime, formatLocaleNumber } from '@/i18n/format.js';
import type { Locale } from '@/i18n/locale.js';
import { workspaceOpenApiGET, workspaceOpenApiPOST } from '@/lib/openapi/client.js';
import { useApiErrorMessage } from '@/lib/errors/use-api-error-message.js';
import { useWorkspaceCatalog } from '@/lib/workspace/context.js';
import { EntityRefLine } from '@/components/app/shared/workspace/entity-ref-line.js';
import { useWorkspaceNodeLabels } from '@/lib/workspace/node-labels.js';
import { workspacePath, workspaceReviewPath } from '@/lib/nav/nav-config.js';
import { cn } from '@/lib/utils.js';
import type { LocaleMessages } from '@/i18n/en.js';
import { AssignEntityTypeDialog } from '@/modules/mappings/components/assign-entity-type-dialog.js';
import { InterpretationConfigDialog } from '@/modules/mappings/components/interpretation-config-panel.js';
import { OntologyUriPicker } from '@/modules/mappings/components/ontology-uri-picker.js';
import { SurfacePhraseCombobox } from '@/modules/mappings/components/surface-phrase-combobox.js';
import { isRdfTypePredicate } from '@/modules/mappings/lib/rdf-type.js';
import { fmt } from '@/i18n/format.js';

type MappingRow = {
  id: string;
  signature: string;
  target_uri: string | null;
  target_kind: string;
  direction: string;
  status: string;
  created_at: string;
};

type TypedFactRow = {
  id: string;
  subject_id: string;
  predicate_uri: string;
  object_entity_id: string | null;
  object_value: string | null;
  from_statement_id: string | null;
  mapping_id: string | null;
};

type MappingsPageCopy = LocaleMessages['mappings']['page'];

function createMappingSchema(signatureRequiredMessage: string, targetUriRequiredMessage: string) {
  return z
    .object({
      signature: z.string(),
      targetUri: z.string(),
      targetKind: z.enum(['property', 'class', 'none']),
      direction: z.enum(['forward', 'reverse', 'n/a']),
    })
    .superRefine((data, ctx) => {
      if (data.targetKind === 'none') {
        return;
      }
      if (!data.signature.trim()) {
        ctx.addIssue({
          code: 'custom',
          path: ['signature'],
          message: signatureRequiredMessage,
        });
      }
      if (!data.targetUri.trim()) {
        ctx.addIssue({
          code: 'custom',
          path: ['targetUri'],
          message: targetUriRequiredMessage,
        });
      }
    });
}

type CreateMappingValues = z.infer<ReturnType<typeof createMappingSchema>>;

const defaultCreateMappingValues: CreateMappingValues = {
  signature: '',
  targetUri: '',
  targetKind: 'property',
  direction: 'forward',
};

export function MappingsWorkspacePanel({ workspaceId }: { workspaceId: string }) {
  const { t, locale } = useI18n();
  const m = t.mappings.page;
  const emptyCell = t.core.common.emptyCell;
  const loc = locale as Locale;
  const id = workspaceId;
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { getWorkspace } = useWorkspaceCatalog();
  const workspaceMeta = getWorkspace(workspaceId);
  const canEditInterpretation = workspaceMeta
    ? ['owner', 'admin'].includes(workspaceMeta.my_role)
    : false;
  const [rows, setRows] = useState<MappingRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [phrases, setPhrases] = useState<string[]>([]);
  const [entityObjectLabels, setEntityObjectLabels] = useState<string[]>([]);
  const [typedFacts, setTypedFacts] = useState<TypedFactRow[]>([]);
  const [mappingStatusBusy, setMappingStatusBusy] = useState<string | null>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignInitialSubject, setAssignInitialSubject] = useState<string | undefined>();
  const [clearTypeBusy, setClearTypeBusy] = useState<string | null>(null);
  const [typeSurfacePhrases, setTypeSurfacePhrases] = useState<string[]>([]);
  const [interpretationDialogOpen, setInterpretationDialogOpen] = useState(false);

  const entityIdsForLabels = typedFacts.flatMap((fact) =>
    [fact.subject_id, fact.object_entity_id].filter((value): value is string => Boolean(value)),
  );
  const entityLabels = useWorkspaceNodeLabels(id, entityIdsForLabels);

  const apiError = useApiErrorMessage();

  const mappingSchema = useMemo(
    () =>
      createMappingSchema(m.validation_signature_required, m.validation_target_uri_required),
    [m.validation_signature_required, m.validation_target_uri_required],
  );

  const createForm = useForm<CreateMappingValues>({
    resolver: zodResolver(mappingSchema),
    defaultValues: defaultCreateMappingValues,
  });

  useEffect(() => {
    if (!createOpen) createForm.reset(defaultCreateMappingValues);
  }, [createOpen, createForm]);

  useEffect(() => {
    const label = searchParams.get('typeMappingLabel')?.trim();
    if (!label) {
      return;
    }
    const targetUri = searchParams.get('typeMappingUri')?.trim() ?? '';
    createForm.setValue('targetKind', 'class');
    createForm.setValue('signature', label);
    createForm.setValue('direction', 'n/a');
    if (targetUri) {
      createForm.setValue('targetUri', targetUri);
    }
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete('typeMappingLabel');
    next.delete('typeMappingUri');
    setSearchParams(next, { replace: true });
  }, [createForm, searchParams, setSearchParams]);

  const watchedTargetKind = createForm.watch('targetKind');
  const watchedSignature = createForm.watch('signature');
  const watchedTargetUri = createForm.watch('targetUri');
  const [alignmentSuggestions, setAlignmentSuggestions] = useState<
    Array<{ uri: string; label: string; relation: string; confidence: number }>
  >([]);
  const signaturePickerOptions =
    watchedTargetKind === 'class' ? entityObjectLabels : phrases;
  const isEntityMapping = watchedTargetKind === 'class';

  const alignmentSuggestKind =
    watchedTargetKind === 'class' || watchedTargetKind === 'property' ? watchedTargetKind : null;

  useEffect(() => {
    if (!createOpen) {
      setAlignmentSuggestions([]);
      return;
    }
    if (!id || !alignmentSuggestKind) {
      setAlignmentSuggestions([]);
      return;
    }
    const label = watchedSignature.trim();
    if (!label) {
      setAlignmentSuggestions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const body = await workspaceOpenApiGET<{
            suggestions: Array<{
              uri: string;
              label: string;
              relation: string;
              confidence: number;
            }>;
          }>(id, 'ontology/alignments/suggest-target-uri', {
            params: {
              query: { label, entity_type: alignmentSuggestKind, limit: 8 },
            },
          });
          const suggestions = body.suggestions ?? [];
          setAlignmentSuggestions(suggestions);
          if (!createForm.getValues('targetUri').trim() && suggestions.length === 1) {
            createForm.setValue('targetUri', suggestions[0].uri);
          }
        } catch {
          setAlignmentSuggestions([]);
        }
      })();
    }, 320);
    return () => window.clearTimeout(timer);
  }, [alignmentSuggestKind, createForm, createOpen, id, watchedSignature]);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [mappingData, phraseData, entityLabelData, factData, interpretationData] =
        await Promise.all([
        workspaceOpenApiGET<{ mappings: MappingRow[] }>(id, 'mappings'),
        workspaceOpenApiGET<{ phrases: string[] }>(id, 'ledger/surface-phrases'),
        workspaceOpenApiGET<{ labels: string[] }>(id, 'ledger/entity-type-object-labels'),
        workspaceOpenApiGET<{ facts: TypedFactRow[] }>(id, 'ledger/typed-facts'),
        workspaceOpenApiGET<{ interpretation: { entity_type_surface_phrases?: string[] } }>(
          id,
          'governance/interpretation',
        ),
      ]);
      setRows(mappingData.mappings);
      setPhrases(phraseData.phrases);
      setEntityObjectLabels(entityLabelData.labels);
      setTypedFacts(factData.facts);
      setTypeSurfacePhrases(interpretationData.interpretation.entity_type_surface_phrases ?? []);
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  }, [apiError, id]);

  useEffect(() => {
    void load();
  }, [load]);

  const updateMappingStatus = useCallback(
    async (mappingId: string, status: 'confirmed' | 'rejected' | 'superseded') => {
      if (!id) return;
      setMappingStatusBusy(mappingId);
      setError(null);
      try {
        await workspaceOpenApiPOST(id, `mappings/${encodeURIComponent(mappingId)}/status`, {
          body: { status },
        });
        await load();
        toast.success(m.toast_mapping_status);
      } catch (err) {
        setError(apiError(err));
      } finally {
        setMappingStatusBusy(null);
      }
    },
    [apiError, id, load, m.toast_mapping_status],
  );

  const onAssignEntityType = useCallback(
    async (values: { subjectId: string; classUri: string }) => {
      if (!id) return;
      setError(null);
      try {
        await workspaceOpenApiPOST(id, 'entity-types/assign', {
          body: {
            assignments: [{ subject_id: values.subjectId.trim(), class_uri: values.classUri.trim() }],
            replace_existing: true,
          },
        });
        await load();
        toast.success(m.toast_type_assigned);
      } catch (err) {
        setError(apiError(err));
        throw err;
      }
    },
    [apiError, id, load, m.toast_type_assigned],
  );

  const clearEntityType = useCallback(
    async (subjectId: string) => {
      if (!id) return;
      if (!window.confirm(fmt(m.clear_type_confirm, { subject: subjectId }))) return;
      setClearTypeBusy(subjectId);
      setError(null);
      try {
        await workspaceOpenApiPOST(id, 'entity-types/clear', {
          body: { subject_ids: [subjectId] },
        });
        await load();
        toast.success(m.toast_type_cleared);
      } catch (err) {
        setError(apiError(err));
      } finally {
        setClearTypeBusy(null);
      }
    },
    [apiError, id, load, m.clear_type_confirm, m.toast_type_cleared],
  );

  async function onCreateMapping(values: CreateMappingValues) {
    if (!id) return;
    setError(null);
    try {
      await workspaceOpenApiPOST(id, 'mappings', {
        body: {
          signature: values.signature.trim(),
          target_uri: values.targetUri.trim() || null,
          target_kind: values.targetKind,
          direction: values.direction,
          status: 'proposed',
        },
      });
      setCreateOpen(false);
      await load();
      toast.success(m.toast_submitted, {
        action: {
          label: m.toast_review_action,
          onClick: () => {
            navigate(workspaceReviewPath(id));
          },
        },
      });
    } catch (err) {
      setError(apiError(err));
    }
  }


  const typePhraseSummary = useMemo(() => {
    if (typeSurfacePhrases.length === 0) return '';
    const max = 12;
    const head = typeSurfacePhrases.slice(0, max).join(', ');
    return typeSurfacePhrases.length > max ? `${head}${t.core.common.ellipsis}` : head;
  }, [t.core.common.ellipsis, typeSurfacePhrases]);

  const mappingColumns = useMemo<DataTableColumn<MappingRow>[]>(
    () => [
      {
        key: 'signature',
        header: m.col_mapping_key,
        render: (row) => <span className="font-mono text-xs">{row.signature}</span>,
      },
      {
        key: 'uri',
        header: m.col_uri,
        render: (row) => (
          <span className="block max-w-[280px] truncate font-mono text-xs">
            {row.target_uri ?? emptyCell}
          </span>
        ),
      },
      {
        key: 'kind',
        header: m.col_kind,
        hideBelow: 'md',
        render: (row) => (
          <span className="text-xs text-muted-foreground">
            {mappingTargetKindLabel(m, row.target_kind)}
          </span>
        ),
      },
      {
        key: 'direction',
        header: m.col_direction,
        hideBelow: 'lg',
        render: (row) => (
          <span className="text-xs text-muted-foreground">
            {mappingDirectionLabel(m, row.direction)}
          </span>
        ),
      },
      {
        key: 'status',
        header: m.col_status,
        render: (row) => <MappingStatus status={row.status} copy={m} />,
      },
      {
        key: 'created',
        header: m.col_created,
        hideBelow: 'lg',
        render: (row) =>
          row.created_at ? formatLocaleDateTime(loc, row.created_at) : emptyCell,
      },
      {
        key: 'actions',
        header: m.col_actions,
        align: 'right',
        render: (row) => {
          const busy = mappingStatusBusy === row.id;
          if (row.status === 'proposed' && id) {
            return (
              <div className="flex flex-wrap justify-end gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  disabled={busy}
                  onClick={() => void updateMappingStatus(row.id, 'confirmed')}
                >
                  {m.action_confirm}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  disabled={busy}
                  onClick={() => void updateMappingStatus(row.id, 'rejected')}
                >
                  {m.action_reject}
                </Button>
                <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
                  <Link to={workspaceReviewPath(id)}>{m.review}</Link>
                </Button>
              </div>
            );
          }
          if (row.status === 'confirmed') {
            return (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={busy}
                onClick={() => void updateMappingStatus(row.id, 'superseded')}
              >
                {m.action_supersede}
              </Button>
            );
          }
          return <span className="text-xs text-muted-foreground">{emptyCell}</span>;
        },
      },
    ],
    [clearEntityType, emptyCell, id, loc, m, mappingStatusBusy, updateMappingStatus],
  );

  const factColumns = useMemo<DataTableColumn<TypedFactRow>[]>(
    () => [
      {
        key: 'predicate',
        header: m.col_predicate,
        render: (fact) => (
          <span className="max-w-[180px] truncate font-mono text-xs">{fact.predicate_uri}</span>
        ),
      },
      {
        key: 'subject',
        header: m.col_subject,
        render: (fact) => <EntityRefLine id={fact.subject_id} labels={entityLabels} />,
      },
      {
        key: 'object',
        header: m.col_object,
        render: (fact) =>
          fact.object_entity_id ? (
            <EntityRefLine id={fact.object_entity_id} labels={entityLabels} />
          ) : (
            <span className="font-mono text-xs">{fact.object_value ?? emptyCell}</span>
          ),
      },
      {
        key: 'actions',
        header: m.col_actions,
        align: 'right',
        render: (fact) => {
          if (!isRdfTypePredicate(fact.predicate_uri)) {
            return <span className="text-xs text-muted-foreground">{emptyCell}</span>;
          }
          const busy = clearTypeBusy === fact.subject_id;
          return (
            <div className="flex flex-wrap justify-end gap-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 px-2 text-xs"
                disabled={busy}
                onClick={() => {
                  setAssignInitialSubject(fact.subject_id);
                  setAssignOpen(true);
                }}
              >
                {m.assign_type}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs text-destructive"
                disabled={busy}
                onClick={() => void clearEntityType(fact.subject_id)}
              >
                {m.action_clear_type}
              </Button>
            </div>
          );
        },
      },
    ],
    [clearEntityType, clearTypeBusy, emptyCell, entityLabels, m],
  );

  return (
    <div
      className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden"
      data-testid="mappings-workspace-panel"
    >
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="button" variant="outline" size="sm" className="h-8" disabled={loading} onClick={() => void load()}>
          {loading ? <PublicIcon name="loader-01" size={14} className="animate-spin" /> : <PublicIcon name="arrow-rotate-left-01" size={14} />}
          {m.refresh}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          onClick={() => {
            setAssignInitialSubject(undefined);
            setAssignOpen(true);
          }}
        >
          <PublicIcon name="tag" size={14} />
          {m.assign_type}
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          data-testid="mappings-open-interpretation-config"
          onClick={() => setInterpretationDialogOpen(true)}
        >
          <PublicIcon name="settings-01" size={14} />
          {m.open_interpretation_config}
        </Button>
        <Button type="button" size="sm" className="h-8" onClick={() => setCreateOpen(true)}>
          <PublicIcon name="plus-01" size={14} />
          {m.new_mapping}
        </Button>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {id && typePhraseSummary ? (
        <p className="text-sm text-muted-foreground" data-testid="mappings-type-phrases-banner">
          {fmt(m.type_phrases_banner, { phrases: typePhraseSummary })}{' '}
          <button
            type="button"
            className="text-foreground underline underline-offset-4"
            onClick={() => setInterpretationDialogOpen(true)}
          >
            {m.type_phrases_banner_link}
          </button>
        </p>
      ) : null}
      {id ? (
        <InterpretationConfigDialog
          workspaceId={id}
          canEdit={canEditInterpretation}
          open={interpretationDialogOpen}
          onOpenChange={setInterpretationDialogOpen}
          onSaved={() => void load()}
        />
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
        <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border">
          <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
            <PublicIcon name="arrows-left-right" size={13} className="shrink-0 text-muted-foreground" />
            <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              {m.section_mappings}
            </span>
            {!loading ? (
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {formatLocaleNumber(loc, rows.length)}
              </span>
            ) : null}
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {loading && rows.length === 0 ? (
              <p className="flex items-center gap-2 px-4 py-6 text-sm text-muted-foreground">
                <PublicIcon name="loader-01" size={14} className="animate-spin" />
                {m.loading}
              </p>
            ) : rows.length === 0 ? (
              <QuietEmpty
                icon="arrows-left-right"
                title={m.mappings_empty_title}
                body={m.mappings_empty_body}
              />
            ) : (
              <DataTable columns={mappingColumns} data={rows} rowKey={(row) => row.id} className="border-0" />
            )}
          </div>
        </section>

        <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border">
          <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
            <PublicIcon name="table" size={13} className="shrink-0 text-muted-foreground" />
            <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
              {m.section_typed_facts}
            </span>
            {!loading ? (
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {formatLocaleNumber(loc, typedFacts.length)}
              </span>
            ) : null}
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            {loading && typedFacts.length === 0 ? (
              <p className="flex items-center gap-2 px-4 py-6 text-sm text-muted-foreground">
                <PublicIcon name="loader-01" size={14} className="animate-spin" />
                {m.loading}
              </p>
            ) : typedFacts.length === 0 ? (
              <QuietEmpty
                icon="table"
                title={m.typed_facts_empty_title}
                body={m.typed_facts_empty_body}
              />
            ) : (
              <DataTable columns={factColumns} data={typedFacts} rowKey={(fact) => fact.id} className="border-0" />
            )}
          </div>
        </section>
      </div>

      {id ? (
        <AssignEntityTypeDialog
          open={assignOpen}
          onOpenChange={setAssignOpen}
          workspaceId={id}
          initialSubjectId={assignInitialSubject}
          onSubmit={onAssignEntityType}
        />
      ) : null}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent
          className="overflow-visible sm:max-w-lg"
          data-testid="mappings-create-dialog"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <Form {...createForm}>
            <form
              className="grid gap-4 sm:grid-cols-2"
              onSubmit={createForm.handleSubmit(onCreateMapping)}
            >
              <DialogHeader className="sm:col-span-2">
                <DialogTitle>{m.create_dialog_title}</DialogTitle>
                <DialogDescription>{m.create_dialog_desc}</DialogDescription>
              </DialogHeader>
              {watchedTargetKind !== 'none' ? (
                <FormField
                  control={createForm.control}
                  name="signature"
                  render={({ field }) => (
                    <FormItem className="sm:col-span-2">
                      <FormLabel>
                        {isEntityMapping ? m.label_entity_object : m.label_signature}
                      </FormLabel>
                      {!isEntityMapping ? (
                        <p className="text-[11px] text-muted-foreground">{m.signature_field_hint}</p>
                      ) : null}
                      <FormControl>
                        <SurfacePhraseCombobox
                          phrases={signaturePickerOptions}
                          value={field.value}
                          onValueChange={field.onChange}
                          disabled={createForm.formState.isSubmitting}
                          placeholder={
                            isEntityMapping
                              ? m.entity_object_combobox_placeholder
                              : m.signature_combobox_placeholder
                          }
                          emptySearchLabel={
                            isEntityMapping
                              ? m.entity_object_combobox_empty
                              : m.signature_combobox_empty
                          }
                          emptyPhrasesLabel={
                            isEntityMapping
                              ? m.entity_object_combobox_no_labels
                              : m.signature_combobox_no_phrases
                          }
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ) : null}
              <FormField
                control={createForm.control}
                name="targetKind"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>{m.label_target_kind}</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={(value: CreateMappingValues['targetKind']) => {
                        field.onChange(value);
                        createForm.setValue('signature', '');
                        if (value === 'class' || value === 'none') {
                          createForm.setValue('direction', 'n/a');
                        } else if (createForm.getValues('direction') === 'n/a') {
                          createForm.setValue('direction', 'forward');
                        }
                      }}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="property">{m.target_kind_property}</SelectItem>
                        <SelectItem value="class">{m.target_kind_class}</SelectItem>
                        <SelectItem value="none">{m.target_kind_none}</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={createForm.control}
                name="targetUri"
                render={({ field }) => (
                  <FormItem className="sm:col-span-2">
                    <FormLabel>
                      {watchedTargetKind === 'class'
                        ? m.label_target_uri_class
                        : watchedTargetKind === 'property'
                          ? m.label_target_uri_property
                          : m.label_target_uri}
                    </FormLabel>
                    <FormControl>
                      {id && (watchedTargetKind === 'property' || watchedTargetKind === 'class') ? (
                        <OntologyUriPicker
                          workspaceId={id}
                          entityType={watchedTargetKind === 'class' ? 'class' : 'property'}
                          value={field.value}
                          onValueChange={field.onChange}
                          disabled={createForm.formState.isSubmitting}
                          placeholder={
                            watchedTargetKind === 'class'
                              ? m.ontology_uri_picker_placeholder_class
                              : m.ontology_uri_picker_placeholder_property
                          }
                          hint={m.ontology_uri_picker_hint}
                          emptySearchLabel={m.ontology_uri_picker_empty}
                        />
                      ) : (
                        <Input
                          placeholder={
                            watchedTargetKind === 'class'
                              ? m.target_uri_placeholder_class
                              : m.target_uri_placeholder
                          }
                          disabled={watchedTargetKind === 'none'}
                          {...field}
                        />
                      )}
                    </FormControl>
                    {alignmentSuggestions.length > 1 ? (
                      <div className="mt-2 space-y-1.5">
                        <p className="text-xs text-muted-foreground">
                          {m.alignment_suggestions_heading}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {alignmentSuggestions.map((row) => (
                            <Button
                              key={`${row.uri}-${row.relation}`}
                              type="button"
                              variant={
                                watchedTargetUri.trim() === row.uri ? 'secondary' : 'outline'
                              }
                              size="sm"
                              className="h-auto max-w-full py-1 text-left"
                              onClick={() => createForm.setValue('targetUri', row.uri)}
                            >
                              <span className="truncate font-medium">
                                {row.label || row.uri}
                              </span>
                              <span className="ml-1 shrink-0 text-[10px] text-muted-foreground">
                                {fmt(m.alignment_suggestions_relation, {
                                  relation: row.relation,
                                })}
                              </span>
                            </Button>
                          ))}
                        </div>
                      </div>
                    ) : null}
                    <FormMessage />
                  </FormItem>
                )}
              />
              {watchedTargetKind === 'property' ? (
                <FormField
                  control={createForm.control}
                  name="direction"
                  render={({ field }) => (
                    <FormItem className="sm:col-span-2">
                      <FormLabel>{m.label_direction}</FormLabel>
                      <Select value={field.value} onValueChange={field.onChange}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="forward">{m.direction_forward}</SelectItem>
                          <SelectItem value="reverse">{m.direction_reverse}</SelectItem>
                          <SelectItem value="n/a">{m.direction_na}</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              ) : null}
              <DialogFooter className="sm:col-span-2">
                <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                  {t.core.common.cancel}
                </Button>
                <Button type="submit" disabled={createForm.formState.isSubmitting}>
                  {createForm.formState.isSubmitting ? m.saving : m.submit_proposal}
                </Button>
              </DialogFooter>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function MappingsPage() {
  const { id } = useParams();
  if (!id) {
    return null;
  }
  return <Navigate to={workspaceOntologyHubPath(id, 'statement')} replace />;
}

function mappingTargetKindLabel(copy: MappingsPageCopy, kind: string): string {
  if (kind === 'property') return copy.target_kind_property;
  if (kind === 'class') return copy.target_kind_class;
  if (kind === 'none') return copy.target_kind_none;
  return kind;
}

function mappingDirectionLabel(copy: MappingsPageCopy, direction: string): string {
  if (direction === 'forward') return copy.direction_forward;
  if (direction === 'reverse') return copy.direction_reverse;
  if (direction === 'n/a') return copy.direction_na;
  return direction;
}

function MappingStatus({ status, copy }: { status: string; copy: MappingsPageCopy }) {
  const statusClass =
    status === 'proposed'
      ? 'badge-status-warning'
      : status === 'confirmed' || status === 'approved' || status === 'active'
        ? 'badge-status-success'
        : '';
  const variant =
    status === 'rejected' || status === 'dismissed'
      ? 'destructive'
      : 'outline';
  const label =
    status === 'proposed'
      ? copy.status_proposed
      : status === 'confirmed'
        ? copy.status_confirmed
        : status === 'approved'
          ? copy.status_approved
          : status === 'active'
            ? copy.status_active
            : status === 'rejected'
              ? copy.status_rejected
              : status === 'dismissed'
                ? copy.status_dismissed
                : status === 'superseded'
                  ? copy.status_superseded
                  : status;
  return (
    <Badge variant={variant} className={cn('text-[11px] font-normal', statusClass)}>
      {label}
    </Badge>
  );
}

function QuietEmpty({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="flex h-full min-h-32 flex-col items-center justify-center px-6 text-center">
      <PublicIcon name={icon} size={18} className="mb-2 text-muted-foreground" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-1 max-w-sm text-[11px] leading-snug text-muted-foreground">{body}</p>
    </div>
  );
}
