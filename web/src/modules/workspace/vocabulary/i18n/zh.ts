export default {
  page: {
    schemes: "词表",
    import: "导入",
    import_title: "导入词表",
    import_body: "上传 SKOS 或 RDF（.ttl、.rdf、.owl）。",
    no_schemes: "尚无词表",
    no_schemes_hint: "导入 .ttl 或 .rdf 后在这里浏览概念。",
    loading_view: "加载词表…",
    loading_schemes: "加载词表…",
    loading_tree: "加载概念…",
    no_concepts: "该词表没有概念。",
    pick_scheme: "选择词表",
    concept: "概念",
    empty_title: "未选择概念",
    empty_body: "在左侧选择一个概念。",
    alt_labels: "别名",
    description: "说明",
    narrower: "下位概念",
    leaf: "没有下位概念。",
    uploading: "正在上传",
    import_ok: "导入完成",
    drop: "拖入文件，或点击选择",
    drop_active: "松开以导入",
    added_summary: "+{nodes} 个概念 · +{edges} 条关系",
    api: {
      fetch_schemes_failed: "加载词表失败",
      fetch_hierarchy_failed: "加载层级失败",
      import_failed: "导入词表失败"
    },
    workspace_required: "词汇表路由需要 workspaceId（VocabularyWorkspaceCatalogProvider）。"
  },
  menu: {
    vocabulary: "词表"
  }
} as const;
