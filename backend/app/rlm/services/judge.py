from __future__ import annotations

from dataclasses import dataclass, field

from app.rlm.adapters.llm_judge import LlmJudge
from app.rlm.domain.models import CandidateIndex
from app.rlm.domain.schemas import Decision, Plan, parse_decision, parse_plan


@dataclass
class JudgeRound:
    plan: Plan | None = None
    decision: Decision | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class JudgeResult:
    rounds: list[JudgeRound]
    degraded: bool
    fallback: dict[str, list[str]] | None = None


def deterministic_fallback_assemble(index: CandidateIndex, *, top_k: int = 5) -> dict[str, list[str]]:
    sorted_candidates = sorted(
        index.candidates,
        key=lambda c: (c.pinned, c.base_score),
        reverse=True,
    )
    selected_ids = [candidate.artifact_id for candidate in sorted_candidates[:top_k]]
    return {"mode": "deterministic", "selected_ids": selected_ids}


def run_llm_judge(
    index: CandidateIndex,
    judge: LlmJudge,
    plan_prompt: str,
    decision_prompt: str,
    *,
    max_llm_calls: int = 4,
    timeout_s: float | None = None,
    max_consecutive_failures: int = 2,
    fallback_top_k: int = 5,
) -> JudgeResult:
    rounds: list[JudgeRound] = []
    consecutive_failures = 0
    llm_calls = 0

    if max_llm_calls <= 0:
        fallback = deterministic_fallback_assemble(index, top_k=fallback_top_k)
        return JudgeResult(rounds=[], degraded=True, fallback=fallback)

    while llm_calls < max_llm_calls:
        round_result = JudgeRound()

        if llm_calls < max_llm_calls:
            try:
                plan_payload = judge.plan(plan_prompt, timeout_s=timeout_s)
                llm_calls += 1
                round_result.plan = parse_plan(plan_payload)
            except Exception as exc:
                round_result.errors.append(f"plan_parse_failed: {exc}")
                consecutive_failures += 1

        if round_result.plan and llm_calls < max_llm_calls:
            try:
                decision_payload = judge.decision(decision_prompt, timeout_s=timeout_s)
                llm_calls += 1
                round_result.decision = parse_decision(decision_payload)
                consecutive_failures = 0
            except Exception as exc:
                round_result.errors.append(f"decision_parse_failed: {exc}")
                consecutive_failures += 1

        rounds.append(round_result)

        if consecutive_failures >= max_consecutive_failures:
            fallback = deterministic_fallback_assemble(index, top_k=fallback_top_k)
            return JudgeResult(rounds=rounds, degraded=True, fallback=fallback)

        if round_result.decision:
            return JudgeResult(rounds=rounds, degraded=False, fallback=None)

        if llm_calls >= max_llm_calls:
            break

    fallback = deterministic_fallback_assemble(index, top_k=fallback_top_k)
    return JudgeResult(rounds=rounds, degraded=True, fallback=fallback)
