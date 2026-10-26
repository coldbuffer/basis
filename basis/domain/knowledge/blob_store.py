"""Content-addressed blob storage per workspace (`workspace_id`)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from basis.domain.errors import AdminError

_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_workspace_segment(workspace_id: str) -> str:
    safe = _SAFE_SEGMENT.sub("_", workspace_id).strip("._") or "workspace"
    if safe in {".", ".."}:
        return "workspace"
    return safe


@dataclass(frozen=True)
class BlobRef:
    workspace_id: str
    sha256: str
    blob_key: str
    byte_size: int


class BlobStore:
    def __init__(self, data_dir: Path) -> None:
        self._root = data_dir / "blobs"
        self._root.mkdir(parents=True, exist_ok=True)

    def _workspace_root(self, workspace_id: str) -> Path:
        return self._root / _safe_workspace_segment(workspace_id)

    def _object_path(self, workspace_id: str, sha256: str) -> Path:
        if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
            raise AdminError(422, "bad_digest", "无效的 blob 摘要")
        prefix = sha256[:2]
        return self._workspace_root(workspace_id) / prefix / sha256

    def blob_key(self, workspace_id: str, sha256: str) -> str:
        safe_workspace = _safe_workspace_segment(workspace_id)
        return f"{safe_workspace}/{sha256[:2]}/{sha256}"

    def put(self, workspace_id: str, data: bytes) -> BlobRef:
        if not workspace_id.strip():
            raise AdminError(422, "bad_workspace_id", "工作区 ID 无效")
        digest = hashlib.sha256(data).hexdigest()
        target = self._object_path(workspace_id, digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            return BlobRef(workspace_id=workspace_id, sha256=digest, blob_key=self.blob_key(workspace_id, digest), byte_size=len(data))

        workspace_dir = self._workspace_root(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".blob-", dir=workspace_dir)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, target)
            try:
                os.chmod(target, 0o644)
            except OSError:
                pass
        except OSError as exc:
            temp_path.unlink(missing_ok=True)
            raise AdminError(500, "blob_write_failed", "无法保存文件内容") from exc
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

        return BlobRef(workspace_id=workspace_id, sha256=digest, blob_key=self.blob_key(workspace_id, digest), byte_size=len(data))

    def read(self, workspace_id: str, blob_key: str) -> bytes:
        path = self._resolve_key(workspace_id, blob_key)
        if not path.is_file():
            raise AdminError(404, "not_found", "文件内容不存在")
        return path.read_bytes()

    def delete(self, workspace_id: str, blob_key: str) -> None:
        path = self._resolve_key(workspace_id, blob_key)
        if path.is_file():
            path.unlink()

    def delete_workspace(self, workspace_id: str) -> None:
        root = self._workspace_root(workspace_id)
        if root.is_dir():
            shutil.rmtree(root)

    def _resolve_key(self, workspace_id: str, blob_key: str) -> Path:
        safe_workspace = _safe_workspace_segment(workspace_id)
        parts = Path(blob_key).parts
        if len(parts) != 3:
            raise AdminError(422, "bad_blob_key", "blob_key 无效")
        key_workspace, prefix, digest = parts
        if key_workspace != safe_workspace:
            raise AdminError(403, "forbidden", "无法访问其他工作区的文件")
        if prefix != digest[:2]:
            raise AdminError(422, "bad_blob_key", "blob_key 无效")
        path = self._object_path(workspace_id, digest)
        resolved = path.resolve()
        workspace_resolved = self._workspace_root(workspace_id).resolve()
        if not str(resolved).startswith(str(workspace_resolved) + os.sep) and resolved != workspace_resolved:
            raise AdminError(403, "forbidden", "无法访问其他工作区的文件")
        return path
