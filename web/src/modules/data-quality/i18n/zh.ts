export default {
  menu: {
    data_quality: "数据质量",
  },
  page: {
    subtitle: "结构约束、陈述策略与治理扫描配置集中在此；智能审查负责执行与待办。",
    tab_overview: "概览",
    tab_structure: "结构约束",
    tab_scan: "扫描配置",
    overview_structure_title: "结构约束（SHACL）",
    overview_structure_body:
      "由 Ontology Hub 本体生成或在此保存的形状图；「开始检查」中的 Hub SHACL 使用已保存版本（与扫描配置中的本体 URI 配对）。",
    overview_mappings_title: "陈述约束（映射）",
    overview_mappings_body: "抽取映射中的谓词策略（如是否允许多值）会在扫描时生成单值类检查，与 SHACL 文件无关。",
    open_mappings: "打开陈述映射",
    open_review: "打开智能审查",
  },
} as const;
