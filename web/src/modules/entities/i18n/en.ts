export default {
  page: {
    subtitle: "Search ledger entities and open a row for statements and derived facts. The rail lists what reasoning wrote back."
  },
  menu: {
    entities: "Ledger"
  },
  ledger: {
    open_evidence: "Evidence",
    no_statements_or_derived: "No statements or derived facts",
    search_chunks: "Search chunks",
    show_statements: "Facts",
    hide_statements: "Hide",
    open_in_graph: "Open in graph",
    open_lineage: "Lineage",
    entity_placeholder: "Entity label or description (empty = recent)",
    search: "Search",
    searching: "Loading…",
    no_entities: "No entities",
    empty_browse_hint: "Search by keyword, or leave empty to browse recent ledger entities.",
    col_entity: "Entity",
    col_kind: "Kind",
    col_description: "Description",
    col_actions: "Actions",
    view_facts: "View facts",
    delete_entity: "Delete entity",
    delete_entity_title: "Delete entity",
    delete_entity_description: "Entity “{label}” will be deleted. The statements below are removed with it and cannot be restored.",
    delete_entity_none: "This entity has no statements. Confirming deletes only the entity.",
    delete_entity_truncated: "Showing the first {shown} of {total} statements.",
    delete_entity_related: "Also deletes {typed} typed facts, {derived} derived facts, and {merges} merge records.",
    delete_entity_confirm: "Delete",
    delete_entity_loading: "Loading statements that will be deleted…",
    entity_facts_title: "Entity facts",
    statements_section: "Statements",
    derived_section: "Derived",
    external_sync_section: "External Connector Sync",
    propose_writeback_button: "Propose write-back",
    proposing_writeback: "Submitting…",
    writeback_review_queued: "Write-back staged for governance review.",
    open_review_queue: "Open in Smart review",
    writeback_applied_toast: "Write-back applied to external source",
    recent_derived_facts: "Recent reasoning",
    recent_derived_facts_hint: "Facts written back by inference, newest first.",
    open_reasoning: "Open reasoning",
    loading_derived_facts: "Loading derived facts…",
    no_derived_facts: "No recent derived facts",
    no_derived_facts_hint: "Run reasoning and write results back to see them here.",
    premise_count: "{count} premises",
    premise_count_one: "1 premise",
    premises_label: "Proof premises",
    entity_count: "{start}–{end} of {total} entities",
    entity_count_empty: "0 entities",
    statement_status_labels: {
      pending: "Pending",
      confirmed: "Confirmed",
      rejected: "Rejected",
      open: "Open"
    },
    chunk_origin_labels: {
      stated: "Stated",
      inferred: "Inferred",
      imported: "Imported"
    },
    evidence: {
      chunk_title: "Chunk",
      statements_title: "Statements in chunk",
      no_statements: "No linked statements",
      no_chunks: "No chunks",
      all_chunks: "All chunks",
      focus_in_graph: "Focus entity in graph",
      token_count: "{count} tok",
      chunk_count: "{count} chunks",
      chunk_count_one: "1 chunk",
      chunk_doc_line: "{title} · #{ordinal}",
      char_range: "{start}–{end}"
    }
  }
} as const;
