"""Map HTTP-style status/detail payloads to AdminError (no FastAPI in core)."""

from __future__ import annotations

from basis.services.errors import AdminError


def _explorer_error_message(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        msg = detail.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg
    return str(detail)


def admin_error_from_http_status(
    status_code: int,
    detail: object,
    *,
    context: str = "explorer",
) -> AdminError:
    if isinstance(detail, dict) and detail.get("code"):
        code = str(detail["code"])
        message = _explorer_error_message(detail)
        return AdminError(status_code, code, message or "Explorer 图接口错误")

    message = _explorer_error_message(detail)

    if context == "semantic_neighborhood":
        if status_code == 404:
            return AdminError(404, "semantic_node_not_found", "语义距离接口未找到所选节点")
        if status_code == 503:
            return AdminError(503, "semantic_unavailable", "当前图谱不支持语义相似度")

    if status_code == 404:
        return AdminError(404, "not_found", message or "资源不存在")
    if status_code == 422:
        return AdminError(422, "validation_error", message or "请求无效")
    if status_code == 503:
        return AdminError(503, "graph_runtime_unavailable", message or "工作区图会话不可用")

    return AdminError(
        status_code,
        "graph_projection_error",
        message or "Explorer 图接口错误",
    )
