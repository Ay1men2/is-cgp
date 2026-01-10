from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.rlm.app.services import (
    RlmServiceError,
    get_rlm_assemble_service,
    get_rlm_run_service,
)


class StubRlmRunService:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def run(self, session_id: str, query: str, options: dict[str, object]) -> dict[str, object]:
        return self.payload


class StubRlmAssembleService:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def assemble(
        self, session_id: str, query: str, options: dict[str, object]
    ) -> dict[str, object]:
        return self.payload


class StubRlmErrorService:
    def __init__(self, error: RlmServiceError):
        self.error = error

    def run(self, session_id: str, query: str, options: dict[str, object]) -> dict[str, object]:
        raise self.error

    def assemble(
        self, session_id: str, query: str, options: dict[str, object]
    ) -> dict[str, object]:
        raise self.error


class RlmApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        app.dependency_overrides.clear()

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_run_contract(self) -> None:
        payload = {
            "run_id": "run-123",
            "status": "ok",
            "program": {"steps": []},
            "glimpses": [{"glimpse": 1}],
            "subcalls": [],
            "final_answer": "answer",
            "citations": [],
            "final": {"answer": "answer"},
        }
        app.dependency_overrides[get_rlm_run_service] = lambda: StubRlmRunService(payload)

        response = self.client.post(
            "/v1/rlm/run",
            json={"session_id": "session-1", "query": "hello", "options": {}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_assemble_contract(self) -> None:
        payload = {
            "run_id": "run-456",
            "status": "ok",
            "assembled_context": {"mode": "program"},
            "rounds_summary": [],
            "rendered_prompt": None,
        }
        app.dependency_overrides[get_rlm_assemble_service] = lambda: StubRlmAssembleService(
            payload
        )

        response = self.client.post(
            "/v1/rlm/assemble",
            json={"session_id": "session-2", "query": "hello", "options": {}},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_empty_query_returns_400(self) -> None:
        error = RlmServiceError(status_code=400, detail="empty_query_not_allowed")
        app.dependency_overrides[get_rlm_run_service] = lambda: StubRlmErrorService(error)

        response = self.client.post(
            "/v1/rlm/run",
            json={"session_id": "session-3", "query": " ", "options": {}},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "empty_query_not_allowed"})


if __name__ == "__main__":
    unittest.main()
