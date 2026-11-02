export default {
  page: {
    schemes: "Schemes",
    import: "Import",
    import_title: "Import vocabulary",
    import_body: "Upload SKOS or RDF (.ttl, .rdf, .owl).",
    no_schemes: "No schemes",
    no_schemes_hint: "Import a .ttl or .rdf file to browse concepts.",
    loading_view: "Loading vocabulary…",
    loading_schemes: "Loading schemes…",
    loading_tree: "Loading concepts…",
    no_concepts: "This scheme has no concepts.",
    pick_scheme: "Select a scheme",
    concept: "Concept",
    empty_title: "No concept selected",
    empty_body: "Select a concept on the left.",
    alt_labels: "Alt labels",
    description: "Description",
    narrower: "Narrower",
    leaf: "No narrower concepts.",
    uploading: "Uploading",
    import_ok: "Imported",
    drop: "Drop a file, or click to choose",
    drop_active: "Drop to import",
    added_summary: "+{nodes} concepts · +{edges} links",
    api: {
      fetch_schemes_failed: "Failed to fetch vocabularies",
      fetch_hierarchy_failed: "Failed to fetch hierarchy",
      import_failed: "Failed to import vocabulary"
    },
    workspace_required: "Vocabulary routes require workspaceId (VocabularyWorkspaceCatalogProvider)."
  },
  menu: {
    vocabulary: "Vocabulary"
  }
} as const;
