from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from basis.services.errors import AdminError
from basis.services.tenancy.admin.store import User
from basis.http.deps import get_current_user

router = APIRouter(tags=["reasoning"])


class ReasonRequest(BaseModel):
    facts: list[str] = Field(min_length=1)
    rules: list[str] = Field(default_factory=list)


@router.post("")
async def reason(
    body: ReasonRequest,
    response: Response,
    user: User = Depends(get_current_user),
) -> dict:
    """Reason. Requires session JWT (`sessionAuth`)."""
    del user, body
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</api/workspaces/{workspace_id}/reasoning/run>; rel="successor-version"'
    raise AdminError(
        410,
        "reason_endpoint_removed",
        "全局 /api/reason 已停用，请使用 POST /api/workspaces/{workspace_id}/reasoning/run（工作区推理工作台）",
    )
