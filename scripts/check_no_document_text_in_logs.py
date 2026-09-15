#!/usr/bin/env python3
"""PII guard: fail if any logging/print call directly references a `.text`
attribute anywhere under decoder/ or web/.

docs/HANDOVER.md §9.5: "no document content in logs, ever ... Write this
into the code as a lint-enforced boundary, not a policy doc." The primary
defense is structural (decoder.schema.Span.__repr__/__str__ redact `.text`
so an accidental `logging.info(f"{span}")` can't leak content); this script
is defense in depth for the more direct mistake of logging `.text` itself.

A line can opt out with a trailing `# pii-ok` comment (e.g. for a test
fixture that deliberately logs known-safe text).

Deliberately stdlib-only and regex-based rather than a full AST-based ruff
plugin: there is no real logging call site to police yet in this scaffold,
so a plugin would be speculative infrastructure. Promote to a proper lint
plugin later if this proves too coarse (e.g. false positives on unrelated
`.text` attributes from other objects).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_CALL_PATTERN = re.compile(r"\b(?:logging\.\w+|logger\.\w+|print)\s*\([^)]*\.text\b")
_OPT_OUT = "# pii-ok"


def find_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if _OPT_OUT in line:
                continue
            if _CALL_PATTERN.search(line):
                violations.append(f"{path}:{lineno}: {line.strip()}")
    return violations


# web/ is scanned too: it is the tier that actually hands document text to
# a browser, so it is where an "just log the span while debugging" mistake
# is most likely to be made and least likely to be noticed.
SCANNED_DIRS = ("decoder", "web")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    violations: list[str] = []
    for directory in SCANNED_DIRS:
        violations.extend(find_violations(repo_root / directory))
    if violations:
        print("PII guard failed — possible document text logged directly:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            "\nIf this is a false positive, add a trailing '# pii-ok' comment to the line.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
