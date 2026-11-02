"""Persist per-workspaces ContextGraph snapshots on disk (not SQL persistence)."""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from basis.services.graph.projection.session import GraphSession

_SAFE_WORKSPACE_ID = re.compile(r"[^a-zA-Z0-9._-]+")
_workspace_write_locks: dict[str, threading.Lock] = {}
_lock_guard = threading.Lock()


@dataclass(frozen=True)
class GraphSnapshotMeta:
    projection_revision: int
    schema_version: int
    saved_at: str
    workspace_id: str


def _workspace_write_lock(workspace_id: str) -> threading.Lock:
    with _lock_guard:
        lock = _workspace_write_locks.get(workspace_id)
        if lock is None:
            lock = threading.Lock()
            _workspace_write_locks[workspace_id] = lock
        return lock


def _fsync_path(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _atomic_replace(tmp: Path, final: Path) -> None:
    _fsync_path(tmp)
    os.replace(tmp, final)


class GraphPersistence:
    """Filesystem snapshot store for projected ContextGraph JSON per workspace."""

    def __init__(self, data_dir: Path) -> None:
        self._dir = data_dir / "graphs"
        self._dir.mkdir(parents=True, exist_ok=True)

    def graph_path(self, workspace_id: str) -> Path:
        safe = _SAFE_WORKSPACE_ID.sub("_", workspace_id).strip("._") or "workspace"
        return self._dir / f"{safe}.json"

    def meta_path(self, workspace_id: str) -> Path:
        return self.graph_path(workspace_id).with_suffix(".json.meta")

    def _path(self, workspace_id: str) -> Path:
        return self.graph_path(workspace_id)

    def _read_meta(self, workspace_id: str) -> GraphSnapshotMeta | None:
        path = self.meta_path(workspace_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return GraphSnapshotMeta(
            projection_revision=int(payload.get("projection_revision", 0)),
            schema_version=int(payload.get("schema_version", 0)),
            saved_at=str(payload.get("saved_at", "")),
            workspace_id=str(payload.get("workspace_id", workspace_id)),
        )

    def _write_meta_atomic(
        self,
        workspace_id: str,
        *,
        projection_revision: int,
        schema_version: int,
    ) -> None:
        final = self.meta_path(workspace_id)
        tmp = final.with_name(f"{final.name}.{uuid.uuid4().hex}.tmp")
        payload = {
            "workspace_id": workspace_id,
            "projection_revision": projection_revision,
            "schema_version": schema_version,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _atomic_replace(tmp, final)

    def load_snapshot(self, workspace_id: str) -> tuple[GraphSession, GraphSnapshotMeta | None]:
        session = GraphSession()
        path = self._path(workspace_id)
        for stale in path.parent.glob(f"{path.name}.*.tmp"):
            try:
                stale.unlink(missing_ok=True)
            except OSError:
                pass
        if path.is_file():
            session.graph.load_from_file(path)
        return session, self._read_meta(workspace_id)

    def load(self, workspace_id: str) -> GraphSession:
        session, _meta = self.load_snapshot(workspace_id)
        return session

    def save(
        self,
        workspace_id: str,
        session: GraphSession,
        *,
        projection_revision: int = 0,
        schema_version: int = 1,
    ) -> GraphSnapshotMeta:
        path = self._path(workspace_id)
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        with _workspace_write_lock(workspace_id):
            session.graph.save_to_file(tmp)
            _atomic_replace(tmp, path)
            self._write_meta_atomic(
                workspace_id,
                projection_revision=projection_revision,
                schema_version=schema_version,
            )
        meta = self._read_meta(workspace_id)
        assert meta is not None
        return meta

    def delete(self, workspace_id: str) -> None:
        with _workspace_write_lock(workspace_id):
            path = self._path(workspace_id)
            if path.is_file():
                path.unlink()
            meta = self.meta_path(workspace_id)
            if meta.is_file():
                meta.unlink()
            hub = self.graph_path(workspace_id).with_suffix(".ontology-hub.json")
            if hub.is_file():
                hub.unlink()
