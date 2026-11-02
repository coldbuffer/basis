"""Demo workspace content pack (续费签字场景, demo_pack_id v2)."""

from __future__ import annotations

DEMO_PACK_ID = "v2"
DEMO_PACK_MARKER = f"demo_pack_id:{DEMO_PACK_ID}"

DEMO_RULE_NAME = "续费订单签字联系人"
DEMO_RULE_BODY = (
    "IF activeAgreement(?us, ?vendor) AND commercialContact(?person, ?vendor) "
    "THEN renewalOrderSignatory(?person, ?vendor)"
)

DEMO_GROUND_FACTS: tuple[str, ...] = (
    "activeAgreement(北辰科技, 云盾科技)",
    "commercialContact(唐悦, 云盾科技)",
)

DEMO_INFERRED_CONCLUSION = "renewalOrderSignatory(唐悦, 云盾科技)"

# surface_phrase → predicate URI
DEMO_MAPPINGS: tuple[tuple[str, str], ...] = (
    ("签署年度服务协议", "urn:basis:pred:activeAgreement"),
    ("项目实施对接", "urn:basis:pred:implementationContact"),
    ("续费报价联系", "urn:basis:pred:commercialContact"),
    ("空调巡检对接", "urn:basis:pred:facilityContact"),
)

# v1 星河场景文档（升级时删除）
LEGACY_DEMO_DOC_KEYS: tuple[str, ...] = (
    "march-hr-2026",
    "june-partner-2026",
    "oct-facility-2026",
    "beihai-handover-2023",
)

PACK_CHECK_EXTERNAL_KEY = "yundun-renewal-2026"

SEED_DOCS: tuple[tuple[str, str, str, str], ...] = (
    (
        "yundun-impl-2025",
        "云盾项目实施对接备忘（2025）.txt",
        "2025-08-01T09:00:00+00:00",
        """云盾项目实施对接备忘（2025）

北辰科技与云盾科技签署年度服务协议。
程浩为云盾科技侧项目实施对接人，负责部署、工单与验收，不负责商务报价与合同签署。
""",
    ),
    (
        "yundun-renewal-2026",
        "云盾2026续费商务函.txt",
        "2026-01-10T10:00:00+00:00",
        """云盾2026续费商务函

云盾科技通知：北辰科技2026年度续费报价请联系商务经理唐悦确认。
本函未指定续费订单签字人姓名。
""",
    ),
    (
        "facility-inspection-2026",
        "总部机房巡检记录（2026）.txt",
        "2026-02-01T08:00:00+00:00",
        """总部机房巡检记录（2026）

北辰科技总部大楼空调外机例行巡检，物业老周为现场对接负责人。
""",
    ),
    (
        "yundun-handover-2022",
        "云盾对接历史纪要（2022）.txt",
        "2022-12-01T09:00:00+00:00",
        """云盾对接历史纪要（2022）

早期云盾项目由孙某对接，孙某已离职。
本纪要未记载现任续费签字人或商务经理姓名。
""",
    ),
)
