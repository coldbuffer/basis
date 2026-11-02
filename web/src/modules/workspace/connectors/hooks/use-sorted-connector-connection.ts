import { useEffect, useMemo, useState } from 'react';
import type { StoredConnection } from '@/modules/workspace/connectors/lib/connector-connections.js';
import {
  connectorConnectionSelectKey,
  resolveStoredConnectionFromOptionKey,
} from '@/modules/workspace/connectors/lib/connector-connections.js';

export function useSortedConnectorConnections(connections: StoredConnection[]) {
  return useMemo(
    () =>
      [...connections].sort((a, b) =>
        a.service.localeCompare(b.service),
      ),
    [connections],
  );
}

export function useConnectorConnectionKey(
  sortedConnections: StoredConnection[],
  resetToken?: unknown,
) {
  const [connectionKey, setConnectionKey] = useState('');

  useEffect(() => {
    if (sortedConnections.length === 0) {
      setConnectionKey('');
      return;
    }
    const keys = sortedConnections.map((c) => connectorConnectionSelectKey(c));
    if (!connectionKey || !keys.includes(connectionKey)) {
      setConnectionKey(keys[0] ?? '');
    }
  }, [sortedConnections, connectionKey, resetToken]);

  const selectedConnection = useMemo(() => {
    if (!connectionKey) {
      return null;
    }
    return resolveStoredConnectionFromOptionKey(connectionKey, sortedConnections);
  }, [connectionKey, sortedConnections]);

  return { connectionKey, setConnectionKey, selectedConnection };
}
