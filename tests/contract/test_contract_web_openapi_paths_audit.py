"""S0: web/src must not embed legacy /api/* literals."""

import subprocess
import sys
from pathlib import Path


def test_web_openapi_path_audit_script() -> None:
    root = Path(__file__).resolve().parents[2]
    script = root / "scripts" / "audit" / "audit-web-openapi-paths.mjs"
    result = subprocess.run(
        ["node", str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
