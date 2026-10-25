export default {
  page: {
    alerts_title: "Active alerts",
    alerts_empty: "No active alerts",
    view_all_alerts: "View all alerts",
    dismiss_all: "Dismiss all",
    refresh: "Refresh",
    dismiss_aria: "Dismiss",
    stream_failed: "Alerts stream failed ({status})",
    stream_no_body: "No alerts stream body",
    severity_critical: "Critical",
    severity_warning: "Warning",
    severity_info: "Info",
    kind_labels: {
      "governance.proposal_proposed": "Ontology proposal",
      "processing.failed": "Processing failed",
      "governance.tripped": "Governance rule",
      sync_failed: "Ingest sync failed"
    },
    kind_llm_fallback: "LLM ({code})",
    view_proposal: "View proposal",
    view_sources: "Open sources",
    view_review: "Open Smart review",
    view_decisions: "Open decisions",
    view_settings: "Open workspace settings",
    view_processing_job: "Open processing job",
    api_docs_link: "Alerts API (OpenAPI)",
    stream_live: "Live",
    episode_group_aria: "Alerts by kind",
    copy_episode_link: "Copy alert link",
    copy_episode_aria: "Copy shareable link to this alert episode",
    governance_tripped_code: "Gate code: {code}",
    governance_tripped_decision: "Decision {id}",
    governance_tripped_review_item: "Review item {id}",
    governance_tripped_proposal: "Proposal {id}",
    governance_tripped_shacl: "{count} SHACL violations",
    processing_failed_job: "Job {id}",
    processing_failed_code: "Error {code}",
    sync_failed_source: "Source {id}",
    subtitle:
      "Processing failures, statement conflicts, ontology proposals, and governance notifications for this workspace."
  },
  menu: {
    alerts: "Alerts"
  },
  nav: {
    workspace_alerts: "Workspace alerts"
  }
} as const;
