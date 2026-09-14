"""The single public entry point for producing a user-facing Answer.

Pipeline (docs/HANDOVER.md §5): intake -> retrieve -> reason (draft) ->
verify (decompose + entail) -> resolve (support state) -> respond (assemble).

Structural guarantee, not just convention: decoder.respond.answer_assembly.
assemble_answer() only accepts list[ResolvedClaim] (decoder.schema), and the
only function that can construct a ResolvedClaim is decoder.resolve.rules.
resolve(). There is no function anywhere in this codebase that turns a raw
AtomicClaim or LLM draft directly into an Answer — verification and
resolution are not optional stops on the way to a response, they are the
only door in.
"""

from __future__ import annotations

from collections.abc import Mapping

from decoder.schema import Answer


def answer_query(
    policy_doc_id: str,
    cis_doc_id: str,
    situation: str,
    provided_inputs: Mapping[str, object] | None = None,
) -> Answer:
    raise NotImplementedError(
        "TODO(M5 — Hero scenario end to end): full pipeline not runnable "
        "until decoder.retrieve.dense (blocked on SPIKE-2 corpus), "
        "decoder.reason, and decoder.verify.entailment are implemented for "
        "real against decoder.llm.ollama_client.OllamaLLMClient (a local "
        "Ollama server, no API key); see docs/HANDOVER.md §5 and §14."
    )
