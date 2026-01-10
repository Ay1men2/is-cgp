from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.rlm.app.services import (
    RlmAssembleService,
    RlmRunService,
    RlmServiceError,
    get_rlm_assemble_service,
    get_rlm_run_service,
)

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
    program: dict[str, Any] = Field(default_factory=dict)
    glimpses: list[dict[str, Any]] = Field(default_factory=list)
    subcalls: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: Optional[str] = None
    citations: list[Any] = Field(default_factory=list)
    final: dict[str, Any] = Field(default_factory=dict)


@router.post("/assemble", response_model=RlmAssembleResp)
def rlm_assemble(
    req: RlmAssembleReq,
    service: RlmAssembleService = Depends(get_rlm_assemble_service),
) -> RlmAssembleResp:
    try:
        result = service.assemble(req.session_id, req.query, req.options)
    except RlmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return RlmAssembleResp(**result)

@router.post("/run", response_model=RlmRunResp)
def rlm_run(
    req: RlmRunReq,
    service: RlmRunService = Depends(get_rlm_run_service),
) -> RlmRunResp:
    try:
        result = service.run(req.session_id, req.query, req.options)
    except RlmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return RlmRunResp(**result)
