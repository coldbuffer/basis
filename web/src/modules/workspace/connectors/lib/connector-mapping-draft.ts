export type ConnectorMappingDraft = {
  provider: string;
    stream_name: string;
  external_table: string;
  primary_key_column: string;
  cursor_column?: string | null;
  label_column: string;
  target_class_uri: string;
  column_mappings: Array<{
    column: string;
    kind: string;
    surface_phrase: string;
    predicate_uri?: string | null;
    writable?: boolean;
  }>;
  sync_mode: string;
  track_deletes: boolean;
  sync_direction: string;
  writeback_mode: string;
  max_rows: number;
  poll_interval_minutes: number;
};
