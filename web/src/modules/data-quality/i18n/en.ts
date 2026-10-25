export default {
  menu: {
    data_quality: "Data quality",
  },
  page: {
    subtitle: "Structure constraints, statement policies, and scan settings live here; Smart review runs checks and queues work.",
    tab_overview: "Overview",
    tab_structure: "Structure",
    tab_scan: "Scan settings",
    overview_structure_title: "Structure (SHACL)",
    overview_structure_body:
      "Shapes generated from the Ontology Hub or saved on this page. Governor SHACL scans use the saved Turtle paired with the ontology URI in scan settings.",
    overview_mappings_title: "Statement rules (mappings)",
    overview_mappings_body:
      "Predicate policies in extraction mappings (e.g. single-valued) drive lightweight scans separate from SHACL Turtle.",
    open_mappings: "Open statement mappings",
    open_review: "Open smart review",
  },
} as const;
