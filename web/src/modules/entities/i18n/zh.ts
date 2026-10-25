export default {
  page: {
    subtitle: "搜索账本实体，点开一行查看陈述与派生事实。右侧是推理最近写回的结果。"
  },
  menu: {
    entities: "实体"
  },
  ledger: {
    open_evidence: "证据",
    no_statements_or_derived: "无陈述或派生事实",
    search_chunks: "搜相关片段",
    show_statements: "事实",
    hide_statements: "收起",
    open_in_graph: "在图谱中打开",
    open_lineage: "溯源血缘",
    entity_placeholder: "实体名称或描述（留空浏览最近）",
    search: "搜索",
    searching: "加载中…",
    no_entities: "无实体",
    empty_browse_hint: "输入关键词搜索，或留空浏览最近创建的账本实体。",
    col_entity: "实体",
    col_kind: "类型",
    col_description: "描述",
    col_actions: "操作",
    view_facts: "查看事实",
    delete_entity: "删除实体",
    delete_entity_title: "删除实体",
    delete_entity_description: "将删除实体「{label}」。下列陈述会一并删除，且不可恢复。",
    delete_entity_none: "该实体没有关联陈述。确认后只删除实体本身。",
    delete_entity_truncated: "仅列出前 {shown} 条，共 {total} 条陈述。",
    delete_entity_related: "同时删除 {typed} 条类型事实、{derived} 条派生事实、{merges} 条合并记录。",
    delete_entity_confirm: "确认删除",
    delete_entity_loading: "正在加载将删除的陈述…",
    entity_facts_title: "实体事实",
    statements_section: "开放陈述",
    derived_section: "推理派生",
    external_sync_section: "外部连接器双向同步",
    propose_writeback_button: "提交写回提案",
    proposing_writeback: "提交中…",
    writeback_review_queued: "写回变更已进入智能审查。",
    open_review_queue: "前往智能审查审批",
    writeback_applied_toast: "已直接写回外部数据源",
    recent_derived_facts: "最近推理",
    recent_derived_facts_hint: "推理写回账本的结果，按时间从新到旧。",
    open_reasoning: "打开推理工作台",
    loading_derived_facts: "加载派生事实…",
    no_derived_facts: "暂无推理派生事实",
    no_derived_facts_hint: "在推理工作台运行并写回后，结果会出现在这里。",
    premise_count: "{count} 条前提",
    premise_count_one: "1 条前提",
    premises_label: "证明前提",
    entity_count: "第 {start}–{end} 条，共 {total} 个实体",
    entity_count_empty: "共 0 个实体",
    statement_status_labels: {
      pending: "待处理",
      confirmed: "已确认",
      rejected: "已驳回",
      open: "开放"
    },
    chunk_origin_labels: {
      stated: "陈述",
      inferred: "推理",
      imported: "导入"
    },
    evidence: {
      chunk_title: "片段",
      statements_title: "本片段陈述",
      no_statements: "无关联陈述",
      no_chunks: "暂无片段",
      all_chunks: "全部片段",
      focus_in_graph: "在图谱中定位实体",
      token_count: "{count} token",
      chunk_count: "{count} 个片段",
      chunk_count_one: "1 个片段",
      chunk_doc_line: "{title} · #{ordinal}",
      char_range: "{start}–{end}"
    }
  }
} as const;
