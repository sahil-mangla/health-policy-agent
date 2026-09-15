from __future__ import annotations

from pathlib import Path

import pytest

from scripts.check_no_document_text_in_logs import SCANNED_DIRS, find_violations


@pytest.mark.parametrize("directory", SCANNED_DIRS)
def test_no_document_text_logged_directly(directory: str) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    assert find_violations(repo_root / directory) == []
