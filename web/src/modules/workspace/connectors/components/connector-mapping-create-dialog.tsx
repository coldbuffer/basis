import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog.js';
import { Button } from '@/components/ui/button.js';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.js';
import { useI18n } from '@/i18n/context.js';
import { ConnectorConnectionPicker } from '@/modules/workspace/connectors/components/connector-connection-picker.js';
import { ConnectorMappingSuggestPanel } from '@/modules/workspace/connectors/components/connector-mapping-suggest-panel.js';
import type { StoredConnection } from '@/modules/workspace/connectors/lib/connector-connections.js';
import {
  useConnectorConnectionKey,
  useSortedConnectorConnections,
} from '@/modules/workspace/connectors/hooks/use-sorted-connector-connection.js';

export type ConnectorMappingCreateTab = 'auto' | 'manual';

type Props = {
  workspaceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialTab?: ConnectorMappingCreateTab;
  connections: StoredConnection[];
  connectionsLoading?: boolean;
  onManualContinue: (connection: StoredConnection | null) => void;
  onApplied?: (createdCount: number) => void;
};

export function ConnectorMappingCreateDialog({
  workspaceId,
  open,
  onOpenChange,
  initialTab = 'auto',
  connections,
  connectionsLoading = false,
  onManualContinue,
  onApplied,
}: Props) {
  const { t } = useI18n();
  const m = t.connectors.page.mappings;
  const s = t.connectors.page.suggest;
  const [tab, setTab] = useState<ConnectorMappingCreateTab>(initialTab);

  const sortedConnections = useSortedConnectorConnections(connections);
  const { connectionKey, setConnectionKey, selectedConnection } = useConnectorConnectionKey(
    sortedConnections,
    open,
  );

  useEffect(() => {
    if (open) {
      setTab(initialTab);
    }
  }, [open, initialTab]);

  const pickerCopy = {
    connection_label: s.connection_label,
    connection_placeholder: s.connection_placeholder,
    loading_connections: s.loading_connections,
    no_connections_hint: s.no_connections_hint,
    open_catalog_button: s.open_catalog_button,
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[85vh] max-w-4xl flex-col overflow-hidden"
        data-testid="connector-mapping-create-dialog"
      >
        <DialogHeader>
          <DialogTitle>{m.create_dialog_title}</DialogTitle>
          <DialogDescription>{m.create_dialog_description}</DialogDescription>
        </DialogHeader>
        <ConnectorConnectionPicker
          workspaceId={workspaceId}
          connections={sortedConnections}
          connectionsLoading={connectionsLoading}
          connectionKey={connectionKey}
          onConnectionKeyChange={setConnectionKey}
          copy={pickerCopy}
        />
        <Tabs
          value={tab}
          onValueChange={(value) => setTab(value as ConnectorMappingCreateTab)}
          className="flex min-h-0 flex-1 flex-col gap-4"
        >
          <TabsList className="grid w-full shrink-0 grid-cols-2">
            <TabsTrigger value="auto" data-testid="create-mapping-tab-auto">
              {m.create_tab_auto}
            </TabsTrigger>
            <TabsTrigger value="manual" data-testid="create-mapping-tab-manual">
              {m.create_tab_manual}
            </TabsTrigger>
          </TabsList>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <TabsContent value="auto" className="mt-0">
              <ConnectorMappingSuggestPanel
                workspaceId={workspaceId}
                selectedConnection={selectedConnection}
                active={open && tab === 'auto'}
                onClose={() => onOpenChange(false)}
                onApplied={onApplied}
              />
            </TabsContent>
            <TabsContent value="manual" className="mt-0 space-y-4">
              <p className="text-sm text-muted-foreground">{m.create_manual_hint}</p>
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  {m.cancel_button}
                </Button>
                <Button
                  disabled={connectionsLoading || !selectedConnection}
                  data-testid="create-mapping-manual-continue-btn"
                  onClick={() => {
                    onOpenChange(false);
                    onManualContinue(selectedConnection);
                  }}
                >
                  {m.create_manual_continue}
                </Button>
              </div>
            </TabsContent>
          </div>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
