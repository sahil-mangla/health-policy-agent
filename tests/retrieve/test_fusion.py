from __future__ import annotations

from decoder.retrieve.fusion import reciprocal_rank_fusion


def test_union_keeps_items_found_by_only_one_list() -> None:
    lexical = ["a", "b"]
    dense = ["c", "d"]
    fused = reciprocal_rank_fusion([lexical, dense])
    assert set(fused) == {"a", "b", "c", "d"}


def test_item_in_both_lists_ranks_above_item_in_only_one() -> None:
    lexical = ["a", "b", "c"]
    dense = ["b", "d", "e"]
    fused = reciprocal_rank_fusion([lexical, dense])
    # "b" appears (rank 2) in both lists, so it should outrank "a" (rank 1
    # in only one list).
    assert fused.index("b") < fused.index("a")


def test_empty_lists_return_empty_result() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_single_list_preserves_relative_order() -> None:
    ranked = ["x", "y", "z"]
    assert reciprocal_rank_fusion([ranked]) == ranked
