from unittest.mock import MagicMock, patch

import pytest

from basis.services.knowledge.pipeline.file_ingest import FileParseError, text_from_bytes


def test_docx_missing_style_falls_back_to_paragraph_text() -> None:
    from semantica.utils.exceptions import ProcessingError

    paragraph = MagicMock()
    paragraph.text = "  正文不受样式影响  "
    document = MagicMock()
    document.paragraphs = [paragraph]

    with (
        patch(
            "semantica.parse.parse_document",
            side_effect=ProcessingError(
                "Failed to parse document: Failed to parse DOCX: 'NoneType' object has no attribute 'name'"
            ),
        ),
        patch("docx.Document", return_value=document),
    ):
        text = text_from_bytes("memo.docx", b"PK fake docx")

    assert text == "正文不受样式影响"


def test_docx_other_parse_error_stays_a_file_parse_error() -> None:
    from semantica.utils.exceptions import ProcessingError

    with (
        patch(
            "semantica.parse.parse_document",
            side_effect=ProcessingError("Failed to parse DOCX: corrupt zip"),
        ),
        pytest.raises(FileParseError, match="corrupt zip"),
    ):
        text_from_bytes("memo.docx", b"PK fake docx")
