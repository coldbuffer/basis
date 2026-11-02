import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/button.js';
import { Checkbox } from '@/components/ui/checkbox.js';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.js';
import { Input } from '@/components/ui/input.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import {
  DataPanel,
  DataPanelBody,
  DataPanelHeader,
} from '@/components/app/shared/console/index.js';
import { useI18n } from '@/i18n/context.js';
import { fmt } from '@/i18n/format.js';
import type { McpToolEntry } from '@/modules/workspace/integration/components/mcp-integration-panel.js';

export type ApiTokenCreateFormValues = {
  name: string;
};

export type OperationAccessFilter = 'read' | 'read_write';
export type GrantChannel = 'mcp' | 'http';

export type HttpOperationEntry = {
  name: string;
  description: string;
  access?: 'read' | 'write';
  path?: string;
};

type Props = {
  formId: string;
  mcpTools: McpToolEntry[];
  httpOperations: HttpOperationEntry[];
  onSubmit: (
    values: ApiTokenCreateFormValues,
    scope: 'read' | 'write',
    grants: { mcp: string[]; http: string[] },
  ) => void | Promise<void>;
};

type OperationRow = {
  name: string;
  description: string;
  access?: 'read' | 'write';
  path?: string;
};

type TokensCopy = {
  operations_filter_read: string;
  operations_filter_read_write: string;
  operations_filter_empty: string;
  operations_select_all: string;
  operations_clear: string;
  operations_selected_count: string;
  operations_access_read: string;
  operations_access_write: string;
  operations_mcp_section_title: string;
  operations_http_section_title: string;
  operations_mcp_section_hint: string;
  operations_http_section_hint: string;
  operations_mcp_required: string;
  operations_http_required: string;
  create_page_title: string;
  create_page_subtitle: string;
};

function rowAccess(row: OperationRow): 'read' | 'write' {
  return row.access === 'write' ? 'write' : 'read';
}

function applyAccessPreset(
  rows: OperationRow[],
  filter: OperationAccessFilter,
): Record<string, boolean> {
  const next: Record<string, boolean> = {};
  for (const row of rows) {
    next[row.name] = filter === 'read_write' ? true : rowAccess(row) === 'read';
  }
  return next;
}

function selectedNames(rows: OperationRow[], selected: Record<string, boolean>): string[] {
  return rows.filter((row) => selected[row.name]).map((row) => row.name);
}

function OperationList({
  rows,
  selectedOps,
  onSelectedOpsChange,
  tokensCopy,
}: {
  rows: OperationRow[];
  selectedOps: Record<string, boolean>;
  onSelectedOpsChange: (next: Record<string, boolean>) => void;
  tokensCopy: TokensCopy;
}) {
  return (
    <div className="divide-y divide-border rounded-md border border-border">
      {rows.length === 0 ? (
        <p className="px-3 py-4 text-sm text-muted-foreground">{tokensCopy.operations_filter_empty}</p>
      ) : (
        rows.map((row) => (
          <label
            key={row.name}
            className="flex cursor-pointer items-start gap-2 px-3 py-2.5 hover:bg-muted/50"
          >
            <Checkbox
              className="mt-0.5"
              checked={selectedOps[row.name] ?? false}
              onCheckedChange={(v) =>
                onSelectedOpsChange({ ...selectedOps, [row.name]: v === true })
              }
            />
            <OperationRowContent row={row} tokensCopy={tokensCopy} />
          </label>
        ))
      )}
    </div>
  );
}

export function ApiTokenCreateForm({ formId, mcpTools, httpOperations, onSubmit }: Props) {
  const { t } = useI18n();
  const mcp = t.integration.mcp;
  const tokensCopy = t.integration.tokens as TokensCopy;
  const [channel, setChannel] = useState<GrantChannel>('mcp');
  const [mcpAccessFilter, setMcpAccessFilter] = useState<OperationAccessFilter>('read');
  const [httpAccessFilter, setHttpAccessFilter] = useState<OperationAccessFilter>('read');
  const [mcpSelected, setMcpSelected] = useState<Record<string, boolean>>({});
  const [httpSelected, setHttpSelected] = useState<Record<string, boolean>>({});

  const sortedMcp = useMemo(
    () => [...mcpTools].sort((a, b) => a.name.localeCompare(b.name)),
    [mcpTools],
  );
  const sortedHttp = useMemo(
    () => [...httpOperations].sort((a, b) => a.name.localeCompare(b.name)),
    [httpOperations],
  );

  const activeRows = channel === 'mcp' ? sortedMcp : sortedHttp;
  const activeAccessFilter = channel === 'mcp' ? mcpAccessFilter : httpAccessFilter;
  const activeSelected = channel === 'mcp' ? mcpSelected : httpSelected;
  const setActiveAccessFilter = channel === 'mcp' ? setMcpAccessFilter : setHttpAccessFilter;
  const setActiveSelected = channel === 'mcp' ? setMcpSelected : setHttpSelected;
  const activeTestPrefix = channel === 'mcp' ? 'api-token-mcp' : 'api-token-http';

  useEffect(() => {
    if (sortedMcp.length === 0) {
      setMcpSelected({});
      return;
    }
    setMcpSelected(applyAccessPreset(sortedMcp, mcpAccessFilter));
  }, [sortedMcp, mcpAccessFilter]);

  useEffect(() => {
    if (sortedHttp.length === 0) {
      setHttpSelected({});
      return;
    }
    setHttpSelected(applyAccessPreset(sortedHttp, httpAccessFilter));
  }, [sortedHttp, httpAccessFilter]);

  const selectedCount = activeRows.filter((row) => activeSelected[row.name]).length;

  const schema = z.object({
    name: z.string().trim().min(1).max(64),
  });

  const form = useForm<ApiTokenCreateFormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '' },
  });

  function applyActivePreset() {
    setActiveSelected(applyAccessPreset(activeRows, activeAccessFilter));
  }

  function onAccessFilterChange(value: string) {
    const next = value as OperationAccessFilter;
    setActiveAccessFilter(next);
    setActiveSelected(applyAccessPreset(activeRows, next));
  }

  async function handleSubmit(values: ApiTokenCreateFormValues) {
    const mcp = selectedNames(sortedMcp, mcpSelected);
    const http = selectedNames(sortedHttp, httpSelected);
    if (mcp.length === 0) {
      form.setError('name', { message: tokensCopy.operations_mcp_required });
      return;
    }
    if (http.length === 0) {
      form.setError('name', { message: tokensCopy.operations_http_required });
      return;
    }
    const hasWrite =
      sortedMcp.some((row) => mcp.includes(row.name) && rowAccess(row) === 'write') ||
      sortedHttp.some((row) => http.includes(row.name) && rowAccess(row) === 'write');
    const scope = hasWrite ? 'write' : 'read';
    await onSubmit(values, scope, { mcp, http });
  }

  return (
    <Form {...form}>
      <form id={formId} onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <DataPanel>
          <DataPanelHeader
            title={tokensCopy.create_page_title}
            subtitle={tokensCopy.create_page_subtitle}
          />
          <DataPanelBody className="space-y-4">
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem className="max-w-xl">
                  <FormLabel>{mcp.name_label}</FormLabel>
                  <FormControl>
                    <Input
                      maxLength={64}
                      placeholder={mcp.name_placeholder}
                      data-testid="api-token-name-input"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <Tabs
              value={channel}
              onValueChange={(value) => setChannel(value as GrantChannel)}
              className="gap-3"
            >
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <TabsList>
                  <TabsTrigger value="mcp" data-testid="api-token-channel-mcp">
                    {tokensCopy.operations_mcp_section_title}
                  </TabsTrigger>
                  <TabsTrigger value="http" data-testid="api-token-channel-http">
                    {tokensCopy.operations_http_section_title}
                  </TabsTrigger>
                </TabsList>

                <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                  <Tabs value={activeAccessFilter} onValueChange={onAccessFilterChange}>
                    <TabsList className="h-8">
                      <TabsTrigger
                        value="read"
                        className="px-2.5 text-xs"
                        data-testid={`${activeTestPrefix}-filter-read`}
                      >
                        {tokensCopy.operations_filter_read}
                      </TabsTrigger>
                      <TabsTrigger
                        value="read_write"
                        className="px-2.5 text-xs"
                        data-testid={`${activeTestPrefix}-filter-read-write`}
                      >
                        {tokensCopy.operations_filter_read_write}
                      </TabsTrigger>
                    </TabsList>
                  </Tabs>
                  <Button type="button" variant="outline" size="sm" onClick={applyActivePreset}>
                    {tokensCopy.operations_select_all}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setActiveSelected({})}
                  >
                    {tokensCopy.operations_clear}
                  </Button>
                  <span className="text-xs text-muted-foreground tabular-nums">
                    {fmt(tokensCopy.operations_selected_count, { count: selectedCount })}
                  </span>
                </div>
              </div>

              <p className="text-xs text-muted-foreground">
                {channel === 'mcp'
                  ? tokensCopy.operations_mcp_section_hint
                  : tokensCopy.operations_http_section_hint}
              </p>

              <TabsContent value="mcp" className="mt-0">
                <OperationList
                  rows={sortedMcp}
                  selectedOps={mcpSelected}
                  onSelectedOpsChange={setMcpSelected}
                  tokensCopy={tokensCopy}
                />
              </TabsContent>
              <TabsContent value="http" className="mt-0">
                <OperationList
                  rows={sortedHttp}
                  selectedOps={httpSelected}
                  onSelectedOpsChange={setHttpSelected}
                  tokensCopy={tokensCopy}
                />
              </TabsContent>
            </Tabs>
          </DataPanelBody>
        </DataPanel>
      </form>
    </Form>
  );
}

function OperationRowContent({
  row,
  tokensCopy,
}: {
  row: OperationRow;
  tokensCopy: Pick<TokensCopy, 'operations_access_read' | 'operations_access_write'>;
}) {
  const access = rowAccess(row);
  return (
    <span className="min-w-0 flex-1 space-y-0.5">
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-xs text-foreground">{row.name}</span>
        <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {access === 'write' ? tokensCopy.operations_access_write : tokensCopy.operations_access_read}
        </span>
      </span>
      {row.path ? (
        <span className="block font-mono text-[10px] text-muted-foreground">{row.path}</span>
      ) : null}
      {row.description && row.description !== row.name ? (
        <span className="block text-xs leading-snug text-muted-foreground">{row.description}</span>
      ) : null}
    </span>
  );
}
