from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.config import settings
from app.rlm.adapters.inference_vllm import InferenceVllmAdapter
from app.rlm.adapters.repos_sql import RlmRepoSQL
from app.rlm.domain.models import CandidateIndex
from app.rlm.services.retrieval import build_candidate_index


class RootLMClient(Protocol):
    def generate_program(
        self,
        index: CandidateIndex,
        policy: dict[str, Any],
        limits: dict[str, Any],
        options: dict[str, Any],
    ) -> "RootLMProgramResult":
        ...

    def generate_final(
        self,
        index: CandidateIndex,
        evidence: list[dict[str, Any]],
        subcalls: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> "RootLMFinalResult":
        ...


class ProgramExecutor(Protocol):
    def execute(
        self,
        program: dict[str, Any],
        index: CandidateIndex,
        options: dict[str, Any],
    ) -> "ExecutionResult":
        ...


@dataclass
class RootLMProgramResult:
    program: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


@dataclass
class RootLMFinalResult:
    final: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None


@dataclass
class ExecutionResult:
    events: list[dict[str, Any]] = field(default_factory=list)
    glimpses: list[dict[str, Any]] = field(default_factory=list)
    subcalls: list[dict[str, Any]] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    run_id: str
    status: str
    final: dict[str, Any]
    program: dict[str, Any] = field(default_factory=dict)
    glimpses: list[dict[str, Any]] = field(default_factory=list)
    subcalls: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str | None = None
    citations: list[Any] = field(default_factory=list)


class MockRootLM:
    def generate_program(
        self,
        index: CandidateIndex,
        policy: dict[str, Any],
        limits: dict[str, Any],
        options: dict[str, Any],
    ) -> RootLMProgramResult:
        candidate_ids = [candidate.artifact_id for candidate in index.candidates]
        program = options.get("program")
        if program is None:
            program = {
                "policy": policy,
                "limits": limits,
                "candidate_ids": candidate_ids,
                "steps": [],
            }
        meta = {
            "mode": "mock",
            "policy": policy,
            "limits": limits,
        }
        return RootLMProgramResult(program=program, meta=meta, raw={"mock": True})

    def generate_final(
        self,
        index: CandidateIndex,
        evidence: list[dict[str, Any]],
        subcalls: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> RootLMFinalResult:
        answer = options.get("final_answer")
        if answer is None:
            answer = f"Mock answer for: {index.query}"
        final = {
            "answer": answer,
            "citations": list(options.get("citations") or []),
            "evidence_count": len(evidence),
            "subcall_count": len(subcalls),
        }
        return RootLMFinalResult(final=final, meta={"mode": "mock"}, raw={"mock": True})


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if not cleaned:
        return None
    match = _JSON_FENCE_RE.search(cleaned)
    if match:
        cleaned = match.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    return None


def _resolve_vllm_config(options: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_url": options.get("vllm_base_url") or settings.vllm_base_url,
        "api_key": options.get("vllm_api_key") or settings.vllm_api_key,
        "model": options.get("vllm_model") or settings.vllm_model,
        "max_tokens": options.get("vllm_max_tokens") or settings.vllm_max_tokens,
        "temperature": options.get("vllm_temperature") or settings.vllm_temperature,
    }


class VllmRootLM:
    def __init__(self, *, base_url: str, api_key: str | None, model: str | None,
                 max_tokens: int | None, temperature: float | None) -> None:
        if not base_url:
            raise ValueError("VLLM_BASE_URL is required when RLM_ROOTLM_BACKEND=vllm")
        self._adapter = InferenceVllmAdapter(
            base_url=base_url,
            api_key=api_key,
            default_model=model,
            default_max_tokens=max_tokens,
            default_temperature=temperature,
        )

    def generate_program(
        self,
        index: CandidateIndex,
        policy: dict[str, Any],
        limits: dict[str, Any],
        options: dict[str, Any],
    ) -> RootLMProgramResult:
        candidate_ids = [candidate.artifact_id for candidate in index.candidates]
        payload = {
            "query": index.query,
            "policy": policy,
            "limits": limits,
            "candidate_ids": candidate_ids,
        }
        prompt = (
            "You are RootLM. Return JSON only.\n"
            "Schema: {\"program\": {\"steps\": [], \"candidate_ids\": [], \"policy\": {}, \"limits\": {}}}\n"
            f"Input: {json.dumps(payload, ensure_ascii=False)}"
        )
        raw_text = self._adapter.generate(prompt)
        parsed = _extract_json_payload(raw_text)
        if parsed is None:
            program = {
                "policy": policy,
                "limits": limits,
                "candidate_ids": candidate_ids,
                "steps": [],
            }
            return RootLMProgramResult(
                program=program,
                meta={"mode": "vllm", "parsed": False},
                raw={"text": raw_text},
            )
        return RootLMProgramResult(
            program=parsed.get("program") or parsed,
            meta={"mode": "vllm", "parsed": True},
            raw=parsed,
        )

    def generate_final(
        self,
        index: CandidateIndex,
        evidence: list[dict[str, Any]],
        subcalls: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> RootLMFinalResult:
        payload = {
            "query": index.query,
            "evidence": evidence,
            "subcalls": subcalls,
        }
        prompt = (
            "You are RootLM. Return JSON only.\n"
            "Schema: {\"final\": {\"answer\": \"\", \"citations\": []}}\n"
            f"Input: {json.dumps(payload, ensure_ascii=False)}"
        )
        raw_text = self._adapter.generate(prompt)
        parsed = _extract_json_payload(raw_text)
        if parsed is None:
            final = {"answer": raw_text.strip(), "citations": []}
            return RootLMFinalResult(
                final=final,
                meta={"mode": "vllm", "parsed": False},
                raw={"text": raw_text},
            )
        return RootLMFinalResult(
            final=parsed.get("final") or parsed,
            meta={"mode": "vllm", "parsed": True},
            raw=parsed,
        )


class MockExecutor:
    def execute(
        self,
        program: dict[str, Any],
        index: CandidateIndex,
        options: dict[str, Any],
    ) -> ExecutionResult:
        return ExecutionResult(
            events=list(options.get("events") or []),
            glimpses=list(options.get("glimpses") or []),
            subcalls=list(options.get("subcalls") or []),
            variables=dict(options.get("vars") or {}),
            status=str(options.get("executor_status") or "ok"),
            meta={"mode": "mock", "program_summary": program.get("steps")},
        )


def _build_evidence(
    events: list[dict[str, Any]],
    glimpses: list[dict[str, Any]],
    subcalls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {"events": events},
        {"glimpses": glimpses},
        {"subcalls": subcalls},
    ]


def _select_rootlm(options: dict[str, Any]) -> RootLMClient:
    backend = str(options.get("rootlm_backend") or settings.rlm_rootlm_backend or "mock")
    backend = backend.strip().lower()
    if backend == "vllm":
        config = _resolve_vllm_config(options)
        return VllmRootLM(
            base_url=config["base_url"],
            api_key=config["api_key"],
            model=config["model"],
            max_tokens=config["max_tokens"],
            temperature=config["temperature"],
        )
    if backend in {"mock", ""}:
        return MockRootLM()
    raise ValueError(f"unsupported rootlm backend: {backend}")


def run_rlm(
    repo: RlmRepoSQL,
    session_id: str,
    query: str,
    options: dict[str, Any] | None = None,
    *,
    rootlm: RootLMClient | None = None,
    executor: ProgramExecutor | None = None,
) -> RunResult:
    options = options or {}
    rootlm = rootlm or _select_rootlm(options)
    executor = executor or MockExecutor()

    index = build_candidate_index(repo, session_id, query, options)
    run_id = repo.insert_run(
        session_id=session_id,
        query=query,
        options=options,
        candidate_index=index.model_dump(),
    )

    status = "ok"
    errors: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "round0": {
            "candidate_count": len(index.candidates),
        }
    }
    program: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    glimpses: list[dict[str, Any]] = []
    glimpses_meta: list[dict[str, Any]] = []
    subcalls: list[dict[str, Any]] = []
    final: dict[str, Any] = {}
    final_answer: str | None = None
    citations: list[Any] = []
    evidence: list[dict[str, Any]] = _build_evidence(events, glimpses, subcalls)

    try:
        policy = dict(options.get("policy") or {})
        limits = dict(options.get("limits") or {})
        program_result = rootlm.generate_program(index, policy, limits, options)
        program = program_result.program
        meta["round1"] = {
            **program_result.meta,
            "policy": policy,
            "limits": limits,
            "stage": "plan",
        }
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round1", "error": str(exc)})

    repo.update_run_payload(
        run_id,
        program=program,
        meta=meta,
        events=events,
        glimpses=glimpses,
        glimpses_meta=glimpses_meta,
        subcalls=subcalls,
        evidence=evidence,
        final=final,
        final_answer=final_answer,
        citations=citations,
        status=status,
        errors=errors,
    )

    if status != "ok":
        return RunResult(
            run_id=run_id,
            status=status,
            final=final,
            program=program,
            glimpses=glimpses,
            subcalls=subcalls,
            final_answer=final_answer,
            citations=citations,
        )

    try:
        execution = executor.execute(program, index, options)
        events = list(execution.events)
        glimpses = list(execution.glimpses)
        glimpses_meta = list(options.get("glimpses_meta") or [])
        if not glimpses_meta:
            glimpses_meta = [
                item.get("glimpse_meta")
                for item in glimpses
                if isinstance(item, dict) and item.get("glimpse_meta")
            ]
        subcalls = list(execution.subcalls)
        evidence = _build_evidence(events, glimpses, subcalls)
        meta["round2"] = {
            **execution.meta,
            "vars": dict(execution.variables),
            "status": execution.status,
            "stage": "examine",
        }
        status = execution.status or status
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round2", "error": str(exc)})

    repo.update_run_payload(
        run_id,
        program=program,
        meta=meta,
        events=events,
        glimpses=glimpses,
        glimpses_meta=glimpses_meta,
        subcalls=subcalls,
        evidence=evidence,
        final=final,
        final_answer=final_answer,
        citations=citations,
        status=status,
        errors=errors,
    )

    if status != "ok":
        return RunResult(
            run_id=run_id,
            status=status,
            final=final,
            program=program,
            glimpses=glimpses,
            subcalls=subcalls,
            final_answer=final_answer,
            citations=citations,
        )

    try:
        evidence = _build_evidence(events, glimpses, subcalls)
        final_result = rootlm.generate_final(index, evidence, subcalls, options)
        final = final_result.final
        final_answer = str(final.get("answer")) if final.get("answer") is not None else None
        citations = list(final.get("citations") or [])
        meta["round3"] = {
            **final_result.meta,
            "evidence_items": len(evidence),
            "stage": "decision",
        }
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round3", "error": str(exc)})

    repo.update_run_payload(
        run_id,
        program=program,
        meta=meta,
        events=events,
        glimpses=glimpses,
        glimpses_meta=glimpses_meta,
        subcalls=subcalls,
        evidence=evidence,
        final=final,
        final_answer=final_answer,
        citations=citations,
        status=status,
        errors=errors,
    )

    return RunResult(
        run_id=run_id,
        status=status,
        final=final,
        program=program,
        glimpses=glimpses,
        subcalls=subcalls,
        final_answer=final_answer,
        citations=citations,
    )
