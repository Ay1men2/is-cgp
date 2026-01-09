from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field


class PlanRound(BaseModel):
    round_id: int = Field(ge=1)
    instructions: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    rounds: list[PlanRound] = Field(default_factory=list)
    strategy: str | None = None


class DecisionRound(BaseModel):
    round_id: int = Field(ge=1)
    selected_ids: list[str] = Field(default_factory=list)
    rationale: str | None = None


class Decision(BaseModel):
    rounds: list[DecisionRound] = Field(default_factory=list)
    degraded: bool = False


PLAN_JSON_SCHEMA: dict[str, Any] = Plan.model_json_schema()
DECISION_JSON_SCHEMA: dict[str, Any] = Decision.model_json_schema()


def _extract_json_text(payload: str) -> str:
    text = payload.strip()
    if "```" in text:
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    return text


def _parse_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    text = _extract_json_text(payload)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def parse_plan(payload: str | dict[str, Any]) -> Plan:
    data = _parse_payload(payload)
    return Plan.model_validate(data)


def parse_decision(payload: str | dict[str, Any]) -> Decision:
    data = _parse_payload(payload)
    return Decision.model_validate(data)
