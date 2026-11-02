import json
import threading
from pathlib import Path

import pytest

pytest.importorskip("semantica")

from basis.services.graph.projection.snapshot_store import GraphPersistence
from basis.services.graph.projection.session import GraphSession


def test_incomplete_tmp_does_not_replace_valid_snapshot(tmp_path: Path) -> None:
    workspace_id = "kb-test-1"
    persistence = GraphPersistence(tmp_path)
    session = GraphSession()
    session.add_node("doc-a", "document", content="hello")
    persistence.save(workspace_id, session, projection_revision=1)

    graph_path = persistence.graph_path(workspace_id)
    bad_tmp = graph_path.with_name(f"{graph_path.name}.deadbeef.tmp")
    bad_tmp.write_text("{not valid json", encoding="utf-8")

    loaded, meta = persistence.load_snapshot(workspace_id)
    assert meta is not None
    assert meta.projection_revision == 1
    assert "doc-a" in loaded.graph.nodes


def test_concurrent_saves_produce_valid_json(tmp_path: Path) -> None:
    workspace_id = "kb-concurrent"
    persistence = GraphPersistence(tmp_path)
    errors: list[Exception] = []

    def writer(suffix: str) -> None:
        try:
            session = GraphSession()
            session.add_node(f"doc-{suffix}", "document", content=suffix)
            persistence.save(workspace_id, session, projection_revision=int(suffix))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(str(i),)) for i in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors
    loaded, meta = persistence.load_snapshot(workspace_id)
    json.loads(persistence.graph_path(workspace_id).read_text(encoding="utf-8"))
    assert meta is not None
    assert "doc-" in next(iter(loaded.graph.nodes.keys()))


def test_meta_tracks_projection_revision(tmp_path: Path) -> None:
    persistence = GraphPersistence(tmp_path)
    workspace_id = "kb-meta"
    session = GraphSession()
    session.add_node("n", "document", content="x")
    persistence.save(workspace_id, session, projection_revision=7, schema_version=1)
    _, meta = persistence.load_snapshot(workspace_id)
    assert meta is not None
    assert meta.projection_revision == 7
    assert meta.schema_version == 1
