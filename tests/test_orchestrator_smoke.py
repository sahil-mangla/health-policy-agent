from __future__ import annotations

import pytest

import decoder
import decoder.orchestrator
from decoder.orchestrator import answer_query


def test_package_imports_cleanly() -> None:
    assert decoder.__version__ == "0.1.0"


def test_all_subpackages_import_cleanly() -> None:
    import decoder.eval  # noqa: F401
    import decoder.extract.interfaces  # noqa: F401
    import decoder.intake.interfaces  # noqa: F401
    import decoder.intake.span_store  # noqa: F401
    import decoder.llm.anthropic_client  # noqa: F401
    import decoder.llm.interface  # noqa: F401
    import decoder.reason.interfaces  # noqa: F401
    import decoder.resolve.rules  # noqa: F401
    import decoder.respond.answer_assembly  # noqa: F401
    import decoder.respond.question_generation  # noqa: F401
    import decoder.retrieve.dense  # noqa: F401
    import decoder.retrieve.fusion  # noqa: F401
    import decoder.retrieve.interfaces  # noqa: F401
    import decoder.retrieve.lexical_fts5  # noqa: F401
    import decoder.verify.decompose  # noqa: F401
    import decoder.verify.entailment  # noqa: F401
    import decoder.verify.numeric_check  # noqa: F401
    import decoder.verify.span_containment  # noqa: F401


def test_orchestrator_has_no_fast_path_and_is_not_yet_wired() -> None:
    # Proves the pipeline is wired together (right symbol, right signature)
    # without pretending anything downstream works yet.
    with pytest.raises(NotImplementedError):
        answer_query(
            policy_doc_id="policy-001",
            cis_doc_id="cis-001",
            situation="admitted for surgery, room rent above eligible limit",
        )
