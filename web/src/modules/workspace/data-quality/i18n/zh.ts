export default {
  menu: {
    data_quality: "数据质检",
  },
  page: {
    subtitle: "编辑 SHACL 形状并保存；治理扫描在「扫描配置」中管理。",
    structure_meta: "谓词与类型规则在「语义对齐」配置；扫描结果与待办在「智能审查」。",
    tab_scan: "扫描配置",
    section_scan_hint:
      "定时治理扫描、置信度阈值、SHACL 本体 URI、类型映射关系词。映射页的谓词策略（如单值）会参与轻量扫描，与 SHACL 形状无关。",
    open_mappings: "语义对齐",
    open_review: "智能审查",
    open_scan_settings: "扫描配置",
  },
} as const;
