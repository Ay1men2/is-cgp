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
from app.rlm.services.trace_logger import get_trace_logger

try:
    from app.rlm.services.pipeline_executor import PipelineExecutor
except Exception as exc:  # noqa: BLE001 - optional import fallback
    PipelineExecutor = None
    _PIPELINE_EXECUTOR_IMPORT_ERROR = str(exc)
else:
    _PIPELINE_EXECUTOR_IMPORT_ERROR = None


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
            steps: list[dict[str, Any]] = []
            if candidate_ids:
                first_id = candidate_ids[0]
                steps = [
                    {"action": "select", "selected_ids": [first_id]},
                    {"action": "glimpse", "artifact_id": first_id, "mode": "head", "n": 800},
                ]
            program = {
                "policy": policy,
                "limits": limits,
                "candidate_ids": candidate_ids,
                "steps": steps,
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


def _select_executor(
    executor: ProgramExecutor | None,
    *,
    repo: RlmRepoSQL,
    options: dict[str, Any],
    errors: list[dict[str, Any]],
    meta: dict[str, Any],
) -> ProgramExecutor:
    if executor is not None:
        return executor
    backend = str(options.get("executor_backend") or "real").strip().lower()
    if backend == "mock":
        meta["executor_backend"] = "mock"
        return MockExecutor()
    if PipelineExecutor is None:
        errors.append(
            {
                "stage": "executor_init",
                "error": f"pipeline_executor_import_failed: {_PIPELINE_EXECUTOR_IMPORT_ERROR}",
            }
        )
        meta["executor_backend"] = "mock_fallback"
        return MockExecutor()
    meta["executor_backend"] = "real"
    return PipelineExecutor(repo=repo)


def _normalize_execution(
    execution: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], str, dict[str, Any]]:
    normalized = False

    def _as_list(value: Any) -> list[dict[str, Any]]:
        nonlocal normalized
        if isinstance(value, list):
            return value
        if value is None:
            normalized = True
            return []
        normalized = True
        return []

    def _as_dict(value: Any) -> dict[str, Any]:
        nonlocal normalized
        if isinstance(value, dict):
            return dict(value)
        if value is None:
            normalized = True
            return {}
        normalized = True
        return {}

    if isinstance(execution, dict):
        events = _as_list(execution.get("events"))
        glimpses = _as_list(execution.get("glimpses"))
        subcalls = _as_list(execution.get("subcalls"))
        variables = _as_dict(execution.get("variables"))
        status = execution.get("status")
        meta = _as_dict(execution.get("meta"))
    else:
        events = _as_list(getattr(execution, "events", None))
        glimpses = _as_list(getattr(execution, "glimpses", None))
        subcalls = _as_list(getattr(execution, "subcalls", None))
        variables = _as_dict(getattr(execution, "variables", None))
        status = getattr(execution, "status", None)
        meta = _as_dict(getattr(execution, "meta", None))

    if not isinstance(status, str) or not status:
        status = "ok"
        normalized = True

    if normalized:
        meta["normalized"] = True

    return events, glimpses, subcalls, variables, status, meta


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


def _preview_text(text: str | None, limit: int = 120) -> str | None:
    if text is None:
        return None
    cleaned = str(text).replace("\n", " ").strip()
    if not cleaned:
        return None
    if len(cleaned) > limit:
        return f"{cleaned[:limit]}..."
    return cleaned


def _summarize_plan_trace(program: dict[str, Any], candidate_count: int) -> dict[str, Any]:
    steps = program.get("steps") if isinstance(program, dict) else None
    steps_count = len(steps) if isinstance(steps, list) else 0
    candidate_ids = program.get("candidate_ids") if isinstance(program, dict) else None
    candidate_ids_count = len(candidate_ids) if isinstance(candidate_ids, list) else None
    payload: dict[str, Any] = {
        "steps_count": steps_count,
        "candidate_count": candidate_count,
    }
    if candidate_ids_count is not None:
        payload["candidate_ids_count"] = candidate_ids_count
    if steps:
        first = steps[0]
        if isinstance(first, dict):
            payload["first_step"] = {
                "action": first.get("action"),
                "artifact_id": first.get("artifact_id"),
            }
    return payload


def _summarize_examine_trace(
    events: list[dict[str, Any]],
    glimpses: list[dict[str, Any]],
    subcalls: list[dict[str, Any]],
    executor_status: str,
) -> dict[str, Any]:
    return {
        "events_count": len(events),
        "glimpses_count": len(glimpses),
        "subcalls_count": len(subcalls),
        "executor_status": executor_status,
    }


def _summarize_decision_trace(
    final_answer: str | None,
    citations: list[Any],
    final_payload: dict[str, Any],
) -> dict[str, Any]:
    answer = final_answer
    if answer is None and isinstance(final_payload, dict):
        raw = final_payload.get("answer")
        if raw is not None:
            answer = str(raw)
    preview = _preview_text(answer, 120)
    payload: dict[str, Any] = {"citations_count": len(citations)}
    if preview is not None:
        payload["final_answer_preview"] = preview
    return payload


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


def _normalize_vllm_base_url(value: str) -> str:
    trimmed = value.rstrip("/")
    if trimmed.endswith("/v1"):
        trimmed = trimmed[:-3]
    return trimmed


def _resolve_decision_vllm_config(options: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    config = dict(_resolve_vllm_config(options))
    missing: list[str] = []
    base_url = config.get("base_url")
    if base_url:
        config["base_url"] = _normalize_vllm_base_url(str(base_url))
    if not config.get("base_url"):
        missing.append("VLLM_BASE_URL")
    if not config.get("model"):
        missing.append("VLLM_MODEL")
    if missing:
        return None, f"vllm_missing_config: {', '.join(missing)}"
    return config, None


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
    # NOTE: Decision stage can use vLLM; plan remains mock until a later milestone.
    plan_rootlm = rootlm or MockRootLM()
    decision_backend = str(options.get("rootlm_backend") or settings.rlm_rootlm_backend or "mock")
    decision_backend = decision_backend.strip().lower()
    decision_rootlm: RootLMClient = MockRootLM()
    decision_mode = "mock"
    decision_fallback_reason: str | None = None
    if decision_backend == "vllm":
        config, decision_fallback_reason = _resolve_decision_vllm_config(options)
        if config:
            try:
                decision_rootlm = VllmRootLM(
                    base_url=config["base_url"],
                    api_key=config["api_key"],
                    model=config["model"],
                    max_tokens=config["max_tokens"],
                    temperature=config["temperature"],
                )
                decision_mode = "vllm"
            except Exception as exc:
                decision_fallback_reason = f"vllm_init_failed: {exc}"
                decision_rootlm = MockRootLM()
                decision_mode = "mock"

    index = build_candidate_index(repo, session_id, query, options)
    run_id = repo.insert_run(
        session_id=session_id,
        query=query,
        options=options,
        candidate_index=index.model_dump(),
    )
    trace_logger = get_trace_logger(run_id)

    status = "ok"
    errors: list[dict[str, Any]] = []
    meta: dict[str, Any] = {
        "round0": {
            "candidate_count": len(index.candidates),
        }
    }
    executor = _select_executor(
        executor,
        repo=repo,
        options=options,
        errors=errors,
        meta=meta,
    )
    program: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    glimpses: list[dict[str, Any]] = []
    glimpses_meta: list[dict[str, Any]] = []
    subcalls: list[dict[str, Any]] = []
    final: dict[str, Any] = {}
    final_answer: str | None = None
    citations: list[Any] = []
    evidence: list[dict[str, Any]] = _build_evidence(events, glimpses, subcalls)

    plan_error: dict[str, Any] | None = None
    try:
        policy = dict(options.get("policy") or {})
        limits = dict(options.get("limits") or {})
        program_result = plan_rootlm.generate_program(index, policy, limits, options)
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
        plan_error = {"stage": "round1", "error": str(exc)}

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
    trace_logger.append(
        stage="plan",
        payload=_summarize_plan_trace(program, len(index.candidates)),
        meta={"status": status},
    )
    if plan_error:
        trace_logger.append_error(
            stage="error",
            error=plan_error["error"],
            meta={"round": plan_error["stage"]},
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

    examine_error: dict[str, Any] | None = None
    exec_status = status
    try:
        execution = executor.execute(program, index, options)
        events, glimpses, subcalls, variables, exec_status, exec_meta = _normalize_execution(execution)
        glimpses_meta = list(options.get("glimpses_meta") or [])
        if not glimpses_meta:
            glimpses_meta = [
                item.get("glimpse_meta")
                for item in glimpses
                if isinstance(item, dict) and item.get("glimpse_meta")
            ]
        evidence = _build_evidence(events, glimpses, subcalls)
        meta["round2"] = {
            **exec_meta,
            "vars": dict(variables),
            "status": exec_status,
            "stage": "examine",
        }
        status = exec_status or status
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round2", "error": str(exc)})
        examine_error = {"stage": "round2", "error": str(exc)}

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
    trace_logger.append(
        stage="examine",
        payload=_summarize_examine_trace(events, glimpses, subcalls, exec_status),
        meta={"status": status},
    )
    if examine_error:
        trace_logger.append_error(
            stage="error",
            error=examine_error["error"],
            meta={"round": examine_error["stage"]},
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

    decision_error: dict[str, Any] | None = None
    decision_trace_meta: dict[str, Any] = {"status": status, "mode": decision_mode}
    if decision_fallback_reason:
        decision_trace_meta["fallback_reason"] = decision_fallback_reason
    try:
        evidence = _build_evidence(events, glimpses, subcalls)
        final_result: RootLMFinalResult | None = None
        if decision_mode == "vllm":
            try:
                final_result = decision_rootlm.generate_final(index, evidence, subcalls, options)
            except Exception as exc:
                decision_fallback_reason = f"vllm_request_failed: {exc}"
                decision_mode = "mock"
                decision_rootlm = MockRootLM()
        if final_result is None:
            final_result = decision_rootlm.generate_final(index, evidence, subcalls, options)
        final = final_result.final
        final_answer = str(final.get("answer")) if final.get("answer") is not None else None
        citations = list(final.get("citations") or [])
        round3_meta = {
            **final_result.meta,
            "evidence_items": len(evidence),
            "stage": "decision",
        }
        if decision_fallback_reason:
            round3_meta["fallback_reason"] = decision_fallback_reason
            round3_meta["fallback_from"] = "vllm"
        meta["round3"] = round3_meta
        decision_trace_meta = {"status": status, "mode": round3_meta.get("mode")}
        if decision_fallback_reason:
            decision_trace_meta["fallback_reason"] = decision_fallback_reason
    except Exception as exc:
        status = "error"
        errors.append({"stage": "round3", "error": str(exc)})
        decision_error = {"stage": "round3", "error": str(exc)}

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
    trace_logger.append(
        stage="decision",
        payload=_summarize_decision_trace(final_answer, citations, final),
        meta=decision_trace_meta,
    )
    if decision_error:
        trace_logger.append_error(
            stage="error",
            error=decision_error["error"],
            meta={"round": decision_error["stage"]},
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
