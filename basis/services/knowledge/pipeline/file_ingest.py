"""Turn uploaded files into plain text via semantica ingest/parse."""

from __future__ import annotations

import tempfile
from pathlib import Path


class FileParseError(Exception):
    """User-facing parse failure (missing deps, unsupported format, empty extract)."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def text_from_bytes(filename: str, data: bytes) -> str:
    """Extract UTF-8 text from an uploaded file name + raw bytes."""
    if not data:
        return ""

    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".markdown", ".csv", ".json"}:
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    with tempfile.NamedTemporaryFile(suffix=suffix or ".bin", delete=False) as handle:
        handle.write(data)
        temp_path = Path(handle.name)

    try:
        from semantica.parse import parse_document
        from semantica.utils.exceptions import ProcessingError

        try:
            parsed = parse_document(str(temp_path), method="default")
        except ProcessingError as exc:
            if suffix == ".docx" and _docx_style_name_missing(exc):
                fallback = _docx_paragraph_text(temp_path)
                if fallback.strip():
                    return fallback
            hint = str(exc)
            if "python-docx" in hint or "documents" in hint:
                hint = (
                    "无法解析 Office 文档：请在 Basis 项目目录执行 "
                    "`uv sync`（依赖 semantica[documents]）。"
                )
            elif "pdf" in hint.lower():
                hint = (
                    "无法解析 PDF：请确认已安装 semantica[parse-pdf] 并重新 `uv sync`。"
                )
            raise FileParseError(hint) from exc

        if not isinstance(parsed, dict):
            parsed = {}
        text = parsed.get("full_text") or parsed.get("text") or ""
        if isinstance(text, str) and text.strip():
            return text
        raise FileParseError(f"无法从 {filename} 解析出文本内容")
    finally:
        temp_path.unlink(missing_ok=True)


def _docx_style_name_missing(exc: BaseException) -> bool:
    """Semantica aborts a DOCX when a paragraph style does not resolve."""
    message = str(exc)
    return "DOCX" in message and "NoneType" in message and "name" in message


def _docx_paragraph_text(path: Path) -> str:
    """Read paragraph text without consulting paragraph styles."""
    from docx import Document

    document = Document(str(path))
    paragraphs = [para.text.strip() for para in document.paragraphs if para.text.strip()]
    return "\n\n".join(paragraphs)
