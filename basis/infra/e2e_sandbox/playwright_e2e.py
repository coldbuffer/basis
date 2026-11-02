"""Playwright E2E data directory names (BASIS_DATA_DIR) and helper gating."""

from __future__ import annotations

from pathlib import Path

PLAYWRIGHT_E2E_DATA_DIR = Path("data/e2e")
PLAYWRIGHT_E2E_DESKTOP_DATA_DIR = Path("data/e2e-desktop")

_E2E_LEAF_NAMES = frozenset({"e2e", "e2e-desktop"})


def is_playwright_e2e_data_dir(data_dir: Path) -> bool:
    """True when API runs with Playwright's isolated BASIS_DATA_DIR (enables /_e2e helpers)."""
    parts = data_dir.parts
    if len(parts) >= 2 and parts[-2] == "data" and parts[-1] in _E2E_LEAF_NAMES:
        return True
    # Legacy root-level dirs (pre data/e2e migration).
    if data_dir.name in ("data-e2e", "data-e2e-desktop"):
        return True
    return False
