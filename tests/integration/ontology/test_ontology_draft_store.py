import pytest

pytest.importorskip("semantica")

from basis.services.ontology.persistence.draft_store import get_draft, list_drafts, save_draft
from basis.services.ontology.models import DraftDiff, DraftRequest


def test_save_and_list_drafts() -> None:
    drafts: dict = {}
    body = DraftRequest(
        ontology_uri="http://example.org/o",
        diff=DraftDiff(added_classes=["http://example.org/o#C"]),
        author="a@test",
        summary="add class",
    )
    saved = save_draft(drafts, body)
    assert saved["draft_id"].startswith("draft_")
    listed = list_drafts(drafts, "http://example.org/o")
    assert len(listed) == 1
    assert get_draft(drafts, saved["draft_id"])["summary"] == "add class"
