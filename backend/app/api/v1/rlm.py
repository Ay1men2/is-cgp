from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_engine  # 你已有：返回 Engine（有缓存）
from sqlalchemy.engine import Engine

from app.rlm.adapters.repos_sql import RlmRepoSQL
from app.rlm.services.retrieval import build_candidate_index
from app.rlm.services.runner import run_rlm

router = APIRouter(prefix="/rlm", tags=["rlm"])


class RlmAssembleReq(BaseModel):
    session_id: str
    query: str
    options: dict[str, Any] = Field(default_factory=dict)


class RlmAssembleResp(BaseModel):
    run_id: str
    status: str = "ok"
    assembled_context: dict[str, Any] = Field(default_factory=dict)
    rounds_summary: list[dict[str, Any]] = Field(default_factory=list)
    rendered_prompt: Optional[str] = None


class RlmRunReq(BaseModel):
    session_id: str
    query: str
    options: dict[str, Any] = Field(default_factory=dict)


class RlmRunResp(BaseModel):
    run_id: str
    status: str = "ok"
    final: dict[str, Any] = Field(default_factory=dict)


@router.post("/assemble", response_model=RlmAssembleResp)
def rlm_assemble(req: RlmAssembleReq, engine: Engine = Depends(get_engine)) -> RlmAssembleResp:
    repo = RlmRepoSQL(engine)

    try:
        idx = build_candidate_index(repo, req.session_id, req.query, req.options)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # v0：assembled_context/rounds_summary 先不做，先把环境状态落库
    run_id = repo.insert_run(
        session_id=req.session_id,
        query=req.query,
        options=req.options,
        candidate_index=idx.model_dump(),
    )

    return RlmAssembleResp(
        run_id=run_id,
        status="ok",
        assembled_context={},
        rounds_summary=[],
        rendered_prompt=None,
    )


@router.post("/run", response_model=RlmRunResp)
def rlm_run(req: RlmRunReq, engine: Engine = Depends(get_engine)) -> RlmRunResp:
    repo = RlmRepoSQL(engine)

    try:
        result = run_rlm(repo, req.session_id, req.query, req.options)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RlmRunResp(run_id=result.run_id, status=result.status, final=result.final)
