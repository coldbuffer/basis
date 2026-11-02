import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { PublicIcon } from '@/components/app/shared/primitives/public-icon.js';
import { Button } from '@/components/ui/button.js';
import { Label } from '@/components/ui/label.js';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.js';
import { workspaceConnectorsAuthorizationHref } from '@/modules/workspace/connectors/lib/playground-deep-link.js';
import type { StoredConnection } from '@/modules/workspace/connectors/lib/connector-connections.js';
import {
  connectorConnectionOptionLabel,
  connectorConnectionSelectKey,
} from '@/modules/workspace/connectors/lib/connector-connections.js';

type Copy = {
  connection_label: string;
  connection_placeholder: string;
  loading_connections: string;
  no_connections_hint: string;
  open_catalog_button: string;
};

type Props = {
  workspaceId: string;
  connections: StoredConnection[];
  connectionsLoading?: boolean;
  connectionKey: string;
  onConnectionKeyChange: (key: string) => void;
  copy: Copy;
  selectTestId?: string;
  labelId?: string;
  /** When false, omit label (e.g. parent FormField supplies FormLabel). */
  showLabel?: boolean;
};

export function ConnectorConnectionPicker({
  workspaceId,
  connections,
  connectionsLoading = false,
  connectionKey,
  onConnectionKeyChange,
  copy,
  selectTestId = 'suggest-connection-select',
  labelId = 'connector-mapping-connection',
  showLabel = true,
}: Props) {
  const optionKeys = useMemo(
    () => connections.map((conn) => connectorConnectionSelectKey(conn)),
    [connections],
  );
  const selectValue = optionKeys.includes(connectionKey) ? connectionKey : optionKeys[0];

  if (connectionsLoading) {
    return <p className="text-sm text-muted-foreground">{copy.loading_connections}</p>;
  }
  if (connections.length === 0) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">{copy.no_connections_hint}</p>
        <Button asChild variant="outline" size="sm">
          <Link to={workspaceConnectorsAuthorizationHref(workspaceId)}>
            <PublicIcon name="plug-01" size={14} className="mr-1" />
            {copy.open_catalog_button}
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {showLabel ? <Label htmlFor={labelId}>{copy.connection_label}</Label> : null}
      <Select value={selectValue} onValueChange={onConnectionKeyChange}>
        <SelectTrigger id={labelId} data-testid={selectTestId} className="w-full font-mono text-xs">
          <SelectValue placeholder={copy.connection_placeholder} />
        </SelectTrigger>
        <SelectContent className="max-h-72">
          {connections.map((conn) => {
            const key = connectorConnectionSelectKey(conn);
            return (
              <SelectItem key={key} value={key} className="font-mono text-xs">
                {connectorConnectionOptionLabel(conn)}
              </SelectItem>
            );
          })}
        </SelectContent>
      </Select>
    </div>
  );
}
