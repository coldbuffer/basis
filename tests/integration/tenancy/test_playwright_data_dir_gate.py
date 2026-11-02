"""Gate for Playwright-only API data dirs (`data/e2e`); not browser E2E tests."""

from __future__ import annotations

from pathlib import Path

from basis.infra.e2e_sandbox.playwright_e2e import is_playwright_e2e_data_dir


def test_is_playwright_e2e_data_dir() -> None:
    assert is_playwright_e2e_data_dir(Path("data/e2e"))
    assert is_playwright_e2e_data_dir(Path("data/e2e-desktop"))
    assert is_playwright_e2e_data_dir(Path("/var/app/data/e2e"))
    assert not is_playwright_e2e_data_dir(Path("data"))
    assert not is_playwright_e2e_data_dir(Path("tmp/e2e"))
    assert is_playwright_e2e_data_dir(Path("data-e2e"))
