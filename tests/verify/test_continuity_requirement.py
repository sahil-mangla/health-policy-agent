"""§9.3: a waiting-period claim must carry the continuity_date requirement,
never be WELL_SUPPORTED on document text alone. Pure logic, no model."""

from __future__ import annotations

from decoder.schema import AtomicClaim, ClaimClass, RequiredInput
from decoder.verify.continuity_requirement import (
    CONTINUITY_DATE,
    attach_continuity_requirement,
)


def _claim(
    subject: str,
    predicate: str,
    value: str,
    required_inputs: list[RequiredInput] | None = None,
) -> AtomicClaim:
    return AtomicClaim(
        id="c1",
        subject=subject,
        predicate=predicate,
        value=value,
        claim_class=ClaimClass.DOCUMENT_FACT,
        is_numeric=False,
        verbatim_match=False,
        required_inputs=required_inputs or [],
    )


def test_waiting_period_claim_gets_continuity_date() -> None:
    claim = _claim("the policy", "has a waiting period of", "4 years for PED")
    [updated] = attach_continuity_requirement([claim])
    assert CONTINUITY_DATE in updated.required_inputs


def test_pre_existing_disease_claim_gets_continuity_date() -> None:
    claim = _claim("pre-existing diseases", "are excluded until", "36 months of coverage")
    [updated] = attach_continuity_requirement([claim])
    assert CONTINUITY_DATE in updated.required_inputs


def test_ped_abbreviation_is_matched() -> None:
    claim = _claim("the policy", "excludes", "PED for 48 months")
    [updated] = attach_continuity_requirement([claim])
    assert CONTINUITY_DATE in updated.required_inputs


def test_unrelated_claim_is_untouched() -> None:
    claim = _claim("the policy", "applies a co-payment of", "5%")
    [updated] = attach_continuity_requirement([claim])
    assert updated.required_inputs == []
    assert updated == claim


def test_already_present_is_not_duplicated() -> None:
    claim = _claim(
        "the policy",
        "has a waiting period of",
        "4 years",
        required_inputs=[CONTINUITY_DATE],
    )
    [updated] = attach_continuity_requirement([claim])
    assert updated.required_inputs.count(CONTINUITY_DATE) == 1


def test_applies_regardless_of_claim_class() -> None:
    derived = AtomicClaim(
        id="c2",
        subject="the waiting period",
        predicate="exceeds",
        value=True,
        claim_class=ClaimClass.DERIVED,
        is_numeric=False,
        verbatim_match=True,
    )
    [updated] = attach_continuity_requirement([derived])
    assert CONTINUITY_DATE in updated.required_inputs


def test_other_required_inputs_are_preserved() -> None:
    other = RequiredInput(name="room_tariff", value_type="int", description="₹/day")
    claim = _claim("the policy", "has a waiting period of", "2 years", required_inputs=[other])
    [updated] = attach_continuity_requirement([claim])
    assert other in updated.required_inputs
    assert CONTINUITY_DATE in updated.required_inputs
