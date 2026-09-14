from __future__ import annotations

from pathlib import Path

from scripts.check_no_document_text_in_logs import find_violations


def test_no_document_text_logged_directly() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    violations = find_violations(repo_root / "decoder")
    assert violations == []
