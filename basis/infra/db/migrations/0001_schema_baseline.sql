-- Basis storage schema baseline (greenfield). Future changes: add 0002_*.sql, etc.

-- >>> 0001_admin_baseline.sql

-- Baseline admin schema (formerly inline AdminStore._migrate).

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    deactivated_at TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_active
    ON users(email) WHERE deactivated_at IS NULL;

CREATE TABLE IF NOT EXISTS tokens (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    visibility TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS members (
    workspace_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    added_by TEXT,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL
);

INSERT OR IGNORE INTO settings(key, value) VALUES ('open_registration', 'true');

-- >>> 0002_knowledge_ledger.sql

-- Canonical knowledge ledger and projection metadata (ADR 0001).

CREATE TABLE IF NOT EXISTS ingest_sources (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    secret_ref TEXT,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    source_id TEXT REFERENCES ingest_sources(id),
    external_key TEXT,
    title TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    current_version_id TEXT,
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS documents_source_key_active
    ON documents(workspace_id, source_id, external_key)
    WHERE external_key IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS document_versions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    document_id TEXT NOT NULL REFERENCES documents(id),
    version_no INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    blob_key TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
    source_time TEXT,
    source_time_kind TEXT,
    status TEXT NOT NULL,
    error_code TEXT,
    error_detail_json TEXT,
    created_at TEXT NOT NULL,
    ready_at TEXT,
    UNIQUE(document_id, version_no)
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    version_id TEXT NOT NULL REFERENCES document_versions(id),
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    heading TEXT,
    char_start INTEGER,
    char_end INTEGER,
    token_count INTEGER,
    language TEXT,
    origin TEXT NOT NULL DEFAULT 'stated',
    anchor_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(version_id, ordinal)
);

CREATE TABLE IF NOT EXISTS extraction_drops (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    version_id TEXT NOT NULL REFERENCES document_versions(id),
    chunk_id TEXT REFERENCES chunks(id),
    code TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'drop',
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    canonical_label TEXT,
    description TEXT,
    entity_kind TEXT NOT NULL DEFAULT 'named',
    created_at TEXT NOT NULL,
    invalidated_at TEXT
);

CREATE TABLE IF NOT EXISTS entity_names (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    entity_id TEXT NOT NULL REFERENCES entities(id),
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    language TEXT,
    evidence_id TEXT,
    recorded_at TEXT NOT NULL,
    invalidated_at TEXT
);

CREATE INDEX IF NOT EXISTS entity_names_lookup
    ON entity_names(workspace_id, normalized_value)
    WHERE invalidated_at IS NULL;

CREATE TABLE IF NOT EXISTS statements (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    subject_id TEXT NOT NULL REFERENCES entities(id),
    surface_phrase TEXT NOT NULL,
    object_entity_id TEXT REFERENCES entities(id),
    object_value TEXT,
    object_datatype TEXT,
    confidence REAL,
    status TEXT NOT NULL,
    proposed_by TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    invalidated_at TEXT,
    supersedes_id TEXT REFERENCES statements(id),
    CHECK ((object_entity_id IS NULL) <> (object_value IS NULL))
);

CREATE TABLE IF NOT EXISTS statement_evidence (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    statement_id TEXT NOT NULL REFERENCES statements(id),
    chunk_id TEXT NOT NULL REFERENCES chunks(id),
    quote TEXT NOT NULL,
    quote_start INTEGER,
    quote_end INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(statement_id, chunk_id, quote_start, quote_end)
);

CREATE TABLE IF NOT EXISTS statement_qualifiers (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    statement_id TEXT NOT NULL REFERENCES statements(id),
    role TEXT NOT NULL,
    value TEXT,
    entity_id TEXT REFERENCES entities(id),
    CHECK ((entity_id IS NULL) <> (value IS NULL))
);

CREATE TABLE IF NOT EXISTS time_mentions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    statement_id TEXT NOT NULL REFERENCES statements(id),
    chunk_id TEXT NOT NULL REFERENCES chunks(id),
    text TEXT NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mappings (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    signature TEXT NOT NULL,
    target_uri TEXT,
    target_kind TEXT NOT NULL,
    direction TEXT NOT NULL,
    status TEXT NOT NULL,
    actor_id TEXT REFERENCES users(id),
    why TEXT,
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    supersedes_id TEXT REFERENCES mappings(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS mapping_active_signature
    ON mappings(workspace_id, signature)
    WHERE status = 'confirmed' AND invalidated_at IS NULL;

CREATE TABLE IF NOT EXISTS typed_facts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    subject_id TEXT NOT NULL REFERENCES entities(id),
    predicate_uri TEXT NOT NULL,
    object_entity_id TEXT REFERENCES entities(id),
    object_value TEXT,
    object_datatype TEXT,
    from_statement_id TEXT REFERENCES statements(id),
    mapping_id TEXT REFERENCES mappings(id),
    import_provenance_json TEXT,
    confidence REAL,
    valid_from TEXT,
    valid_to TEXT,
    recorded_at TEXT NOT NULL,
    invalidated_at TEXT,
    supersedes_id TEXT REFERENCES typed_facts(id),
    CHECK ((object_entity_id IS NULL) <> (object_value IS NULL)),
    CHECK (from_statement_id IS NOT NULL OR import_provenance_json IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS derived_facts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    subject_id TEXT NOT NULL REFERENCES entities(id),
    predicate_uri TEXT NOT NULL,
    object_entity_id TEXT REFERENCES entities(id),
    object_value TEXT,
    object_datatype TEXT,
    rule_id TEXT,
    recorded_at TEXT NOT NULL,
    invalidated_at TEXT,
    CHECK ((object_entity_id IS NULL) <> (object_value IS NULL))
);

CREATE TABLE IF NOT EXISTS fact_derivations (
    derived_fact_id TEXT NOT NULL REFERENCES derived_facts(id),
    premise_kind TEXT NOT NULL,
    premise_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (derived_fact_id, ordinal)
);

CREATE TABLE IF NOT EXISTS review_items (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    kind TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by TEXT REFERENCES users(id),
    rationale TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS review_one_open_subject
    ON review_items(workspace_id, kind, subject_type, subject_id)
    WHERE status = 'open';

CREATE TABLE IF NOT EXISTS agent_decisions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    review_item_id TEXT REFERENCES review_items(id),
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    rationale TEXT,
    trace_json TEXT NOT NULL,
    model_ref TEXT,
    created_at TEXT NOT NULL,
    applied_at TEXT,
    supersedes_id TEXT REFERENCES agent_decisions(id)
);

CREATE TABLE IF NOT EXISTS entity_merges (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    source_entity_id TEXT NOT NULL REFERENCES entities(id),
    target_entity_id TEXT NOT NULL REFERENCES entities(id),
    decision_id TEXT REFERENCES agent_decisions(id),
    actor_id TEXT REFERENCES users(id),
    why TEXT,
    created_at TEXT NOT NULL,
    reverted_at TEXT,
    reverted_by TEXT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    kind TEXT NOT NULL,
    subject_type TEXT,
    subject_id TEXT,
    status TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    progress REAL,
    error_code TEXT,
    error_detail_json TEXT,
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    UNIQUE(workspace_id, kind, idempotency_key)
);

CREATE TABLE IF NOT EXISTS embedding_records (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    chunk_id TEXT NOT NULL REFERENCES chunks(id),
    model_ref TEXT NOT NULL,
    dimension INTEGER NOT NULL,
    content_sha256 TEXT NOT NULL,
    vector_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(chunk_id, model_ref)
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    title TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL,
    generation_id TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS chat_citations (
    message_id TEXT NOT NULL REFERENCES chat_messages(id),
    ordinal INTEGER NOT NULL,
    chunk_id TEXT REFERENCES chunks(id),
    evidence_id TEXT REFERENCES statement_evidence(id),
    quote TEXT,
    PRIMARY KEY (message_id, ordinal)
);

CREATE TABLE IF NOT EXISTS projection_state (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id),
    revision INTEGER NOT NULL DEFAULT 0,
    schema_version INTEGER NOT NULL,
    status TEXT NOT NULL,
    last_built_at TEXT,
    last_error_code TEXT
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    scope TEXT NOT NULL,
    workspace_ids_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    last_used_at TEXT,
    revoked_at TEXT
);

-- >>> 0003_api_token_secret.sql

-- Persist API token plaintext for admin re-copy (auth still uses token_hash).
ALTER TABLE api_tokens ADD COLUMN token_secret TEXT;

-- >>> 0005_api_token_allowed_operations.sql

-- Optional JSON list of MCP tool / HTTP grant ids; NULL = unrestricted.
ALTER TABLE api_tokens ADD COLUMN allowed_operations_json TEXT;

-- >>> 0004_kb_search_config.sql

-- Per-workspace retrieval policy. Backends are named explicitly so additional
-- implementations can be added without changing the API contract.

CREATE TABLE IF NOT EXISTS search_configs (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL DEFAULT 1,
    chunk_backend TEXT NOT NULL DEFAULT 'sqlite_ledger',
    vector_backend TEXT NOT NULL DEFAULT 'sqlite_vec',
    embedding_model_id TEXT,
    keyword_enabled INTEGER NOT NULL DEFAULT 1 CHECK (keyword_enabled IN (0, 1)),
    semantic_enabled INTEGER NOT NULL DEFAULT 1 CHECK (semantic_enabled IN (0, 1)),
    default_mode TEXT NOT NULL DEFAULT 'hybrid'
        CHECK (default_mode IN ('keyword', 'semantic', 'hybrid')),
    auto_index INTEGER NOT NULL DEFAULT 1 CHECK (auto_index IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- >>> 0005_chunk_fts.sql

-- Rebuildable full-text projection for canonical chunks.
-- trigram supports substring matching and unsegmented CJK text for queries
-- containing at least three Unicode code points.

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    workspace_id UNINDEXED,
    text,
    tokenize = 'trigram'
);

CREATE TRIGGER IF NOT EXISTS chunks_fts_insert
AFTER INSERT ON chunks
BEGIN
    INSERT INTO chunks_fts(chunk_id, workspace_id, text)
    VALUES (new.id, new.workspace_id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_update
AFTER UPDATE OF text, workspace_id ON chunks
BEGIN
    DELETE FROM chunks_fts WHERE chunk_id = old.id;
    INSERT INTO chunks_fts(chunk_id, workspace_id, text)
    VALUES (new.id, new.workspace_id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_fts_delete
AFTER DELETE ON chunks
BEGIN
    DELETE FROM chunks_fts WHERE chunk_id = old.id;
END;

INSERT INTO chunks_fts(chunk_id, workspace_id, text)
SELECT c.id, c.workspace_id, c.text
FROM chunks c
WHERE NOT EXISTS (
    SELECT 1 FROM chunks_fts f WHERE f.chunk_id = c.id
);

CREATE INDEX IF NOT EXISTS chunks_workspace_created
    ON chunks(workspace_id, created_at DESC);

-- >>> 0006_postgres_search.sql

-- PostgreSQL adds a GiST trigram index for nearest-neighbor text ranking.
-- SQLite keyword search continues to use the FTS5 projection from migration 0005.

-- >>> 0007_processing_jobs.sql

ALTER TABLE jobs ADD COLUMN options_json TEXT;
ALTER TABLE jobs ADD COLUMN result_json TEXT;

CREATE INDEX IF NOT EXISTS jobs_workspace_created
    ON jobs(workspace_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS jobs_active_document_version
    ON jobs(workspace_id, subject_type, subject_id)
    WHERE kind = 'ingest' AND status IN ('queued', 'running');

-- >>> 0008_kb_reasoning_rules.sql

CREATE TABLE IF NOT EXISTS reasoning_rules (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    name TEXT NOT NULL,
    body TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    actor_id TEXT REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX IF NOT EXISTS reasoning_rules_active
    ON reasoning_rules(workspace_id, updated_at DESC)
    WHERE deleted_at IS NULL;

-- >>> 0009_kb_alerts.sql

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    kind TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'warning',
    message TEXT NOT NULL,
    detail_json TEXT,
    created_at TEXT NOT NULL,
    read_at TEXT,
    dismissed_at TEXT
);

CREATE INDEX IF NOT EXISTS alerts_workspace_created
    ON alerts(workspace_id, created_at DESC)
    WHERE dismissed_at IS NULL;

-- >>> 0010_organizations_sso.sql

-- Organizations (customer tenants), SSO config, federated identities, magic links.

CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    auth_policy TEXT NOT NULL DEFAULT 'password_allowed',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS org_members (
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS org_members_user ON org_members(user_id);

CREATE TABLE IF NOT EXISTS org_oidc_configs (
    organization_id TEXT PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    issuer TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT 'openid email profile',
    email_domains_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_federated_identities (
    id TEXT PRIMARY KEY,
    organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    provider TEXT NOT NULL,
    issuer TEXT,
    subject TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS user_federated_identities_unique
    ON user_federated_identities(
        COALESCE(organization_id, ''),
        provider,
        COALESCE(issuer, ''),
        subject
    );

CREATE TABLE IF NOT EXISTS magic_link_tokens (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    organization_id TEXT,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS oauth_state_nonces (
    state_hash TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

ALTER TABLE workspaces ADD COLUMN organization_id TEXT REFERENCES organizations(id);

-- >>> 0011_entity_external_sync.sql

-- Basis Open Connector Protocol (BOCP) & bidirectional entity sync (F-LAKE / F-OPS).

CREATE TABLE IF NOT EXISTS connector_policies (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    allowed_providers_json TEXT NOT NULL DEFAULT '"*"',
    action_policy_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL
);

-- One row per (workspace, service, scope, subject).
-- workspace scope: subject_id ''. end_user scope: Integration / playground subject_id.
CREATE TABLE IF NOT EXISTS connector_connections (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    connection_scope TEXT NOT NULL DEFAULT 'workspace',
    subject_id TEXT NOT NULL DEFAULT '',
    auth_type TEXT NOT NULL,
    connection_config_json TEXT NOT NULL DEFAULT '{}',
    value_encrypted TEXT NOT NULL,
    account_profile_json TEXT NOT NULL DEFAULT '{}',
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, service, connection_scope, subject_id)
);

CREATE TABLE IF NOT EXISTS connector_oauth_configs (
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    value_encrypted TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, service)
);

CREATE TABLE IF NOT EXISTS connector_runs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    operation_kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    ok INTEGER NOT NULL,
    value_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_connector_runs_started
    ON connector_runs(workspace_id, started_at DESC);

CREATE TABLE IF NOT EXISTS source_table_mappings (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES ingest_sources(id) ON DELETE CASCADE,
    stream_name TEXT NOT NULL,
    external_table TEXT NOT NULL,
    stream_params_json TEXT NOT NULL DEFAULT '{}',
    primary_key_column TEXT NOT NULL,
    cursor_column TEXT,
    label_column TEXT NOT NULL,
    target_class_uri TEXT NOT NULL,
    column_mappings_json TEXT NOT NULL,
    sync_mode TEXT NOT NULL DEFAULT 'incremental',
    track_deletes INTEGER NOT NULL DEFAULT 0 CHECK (track_deletes IN (0, 1)),
    checkpoint_json TEXT NOT NULL DEFAULT '{}',
    sync_direction TEXT NOT NULL DEFAULT 'inbound',
    writeback_mode TEXT NOT NULL DEFAULT 'review',
    max_rows INTEGER NOT NULL DEFAULT 10000,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, source_id, external_table)
);

CREATE INDEX IF NOT EXISTS idx_source_table_mappings_workspace_source
    ON source_table_mappings(workspace_id, source_id);

CREATE TABLE IF NOT EXISTS entity_external_refs (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES ingest_sources(id) ON DELETE CASCADE,
    mapping_id TEXT NOT NULL REFERENCES source_table_mappings(id) ON DELETE CASCADE,
    external_table TEXT NOT NULL,
    external_pk TEXT NOT NULL,
    row_hash TEXT NOT NULL,
    last_synced_at TEXT NOT NULL,
    deleted_upstream_at TEXT,
    UNIQUE(workspace_id, source_id, external_table, external_pk)
);

CREATE INDEX IF NOT EXISTS idx_entity_external_refs_workspace_entity
    ON entity_external_refs(workspace_id, entity_id);

CREATE TABLE IF NOT EXISTS entity_sync_outbox (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    external_ref_id TEXT NOT NULL REFERENCES entity_external_refs(id) ON DELETE CASCADE,
    statement_id TEXT REFERENCES statements(id) ON DELETE SET NULL,
    typed_fact_id TEXT REFERENCES typed_facts(id) ON DELETE SET NULL,
    action_kind TEXT NOT NULL,
    patch_json TEXT NOT NULL,
    status TEXT NOT NULL,
    review_item_id TEXT REFERENCES review_items(id) ON DELETE SET NULL,
    decision_id TEXT REFERENCES agent_decisions(id) ON DELETE SET NULL,
    job_id TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    error_code TEXT,
    error_detail_json TEXT,
    created_by TEXT REFERENCES users(id),
    created_at TEXT NOT NULL,
    synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_entity_sync_outbox_workspace_status
    ON entity_sync_outbox(workspace_id, status, created_at);

-- >>> 0012_platform_connector_allowlist.sql

-- Platform-wide BOCP provider allowlist (workspace policies must stay within this ceiling).

INSERT OR IGNORE INTO settings(key, value) VALUES ('connector_allowed_providers', '"*"');

-- >>> 0013_kb_governance_config.sql

-- Per-workspace agent governor schedule (F-GOV-04 Phase B).

CREATE TABLE IF NOT EXISTS governance_configs (
    workspace_id TEXT PRIMARY KEY REFERENCES workspaces(id) ON DELETE CASCADE,
    schema_version INTEGER NOT NULL DEFAULT 1,
    governor_enabled INTEGER NOT NULL DEFAULT 0 CHECK (governor_enabled IN (0, 1)),
    governor_interval_minutes INTEGER NOT NULL DEFAULT 1440 CHECK (governor_interval_minutes >= 0),
    governor_confidence_min REAL NOT NULL DEFAULT 0.75,
    governor_last_run_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- >>> 0014_org_saml_config.sql

-- Organization SAML 2.0 IdP config (F-ACC-07).

CREATE TABLE IF NOT EXISTS org_saml_configs (
    organization_id TEXT PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    idp_entity_id TEXT NOT NULL,
    idp_sso_url TEXT NOT NULL,
    idp_x509_cert TEXT NOT NULL,
    sp_entity_id TEXT,
    email_domains_json TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- >>> 0015_org_saml_signing.sql

-- Optional SP signing for SAML AuthnRequest (F-ACC-07).

ALTER TABLE org_saml_configs ADD COLUMN authn_requests_signed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE org_saml_configs ADD COLUMN sp_x509_cert TEXT;
ALTER TABLE org_saml_configs ADD COLUMN sp_private_key TEXT;

-- >>> 0016_org_saml_slo.sql

-- SAML Single Logout (IdP SLO URL) — F-ACC-07 Phase C.

ALTER TABLE org_saml_configs ADD COLUMN idp_slo_url TEXT;
ALTER TABLE org_saml_configs ADD COLUMN slo_enabled INTEGER NOT NULL DEFAULT 0;
