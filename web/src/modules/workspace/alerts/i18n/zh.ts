export default {
  page: {
    alerts_title: "活跃告警",
    alerts_empty: "当前没有告警",
    view_all_alerts: "查看全部告警",
    dismiss_all: "全部忽略",
    refresh: "刷新",
    dismiss_aria: "忽略",
    stream_failed: "告警流失败（{status}）",
    stream_no_body: "告警流响应体为空",
    severity_critical: "严重",
    severity_warning: "警告",
    severity_info: "信息",
    kind_labels: {
      "governance.proposal_proposed": "本体提案",
      "processing.failed": "处理失败",
      "governance.tripped": "治理规则",
      sync_failed: "采集同步失败"
    },
    kind_llm_fallback: "LLM（{code}）",
    view_proposal: "查看提案",
    view_sources: "打开资料源",
    view_review: "打开智能审查",
    view_decisions: "打开决策记录",
    view_settings: "打开工作区设置",
    view_processing_job: "打开处理任务",
    api_docs_link: "告警 API（OpenAPI）",
    stream_live: "实时",
    episode_group_aria: "按类型分组",
    copy_episode_link: "复制告警链接",
    copy_episode_aria: "复制可分享的告警 episode 链接",
    governance_tripped_code: "门控代码：{code}",
    governance_tripped_decision: "决策 {id}",
    governance_tripped_review_item: "审核项 {id}",
    governance_tripped_proposal: "提案 {id}",
    governance_tripped_shacl: "SHACL 违规 {count} 条",
    processing_failed_job: "任务 {id}",
    processing_failed_code: "错误 {code}",
    sync_failed_source: "来源 {id}",
    subtitle: "当前工作区的处理异常、陈述冲突、本体提案与治理提醒；支持直达对应页面。"
  },
  menu: {
    alerts: "消息提醒"
  },
  nav: {
    workspace_alerts: "工作区告警"
  }
} as const;
