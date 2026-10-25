"""S0: web ↔ operationId audit artifact is fresh."""

import json
import subprocess
import sys
from pathlib import Path


def test_web_operation_id_audit_generates() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "openapi" / "audit-web-operation-ids.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    data = json.loads((root / "openapi/web-openapi-operation-audit.json").read_text())
    entries = data.get("entries") or []
    assert len(entries) >= 40
    scorable = [
        e
        for e in entries
        if e.get("kind") not in ("dynamic", "doc_template")
    ]
    assert len(scorable) >= 35
    matched = sum(1 for e in scorable if e.get("operationId"))
    assert matched / len(scorable) >= 0.85
