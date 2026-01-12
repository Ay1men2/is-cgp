from __future__ import annotations

from app.rlm.adapters.inference_vllm import InferenceVllmAdapter, RetryPolicy


def test_inference_vllm_bounds(monkeypatch) -> None:
    captured = {}

    class DummyClient:
        def chat_completions(self, **kwargs):
            captured.update(kwargs)
            return {"choices": [{"message": {"content": "ok"}}]}

    adapter = InferenceVllmAdapter(
        base_url="http://example.com",
        api_key=None,
        default_model="m1",
        default_max_tokens=128,
        default_temperature=0,
        default_stop=["\n\n", "```", "<END>"],
        default_extra={"stream": False},
        retry=RetryPolicy(timeout_s=20.0, max_retries=1, backoff_s=0.5),
    )
    adapter._client = DummyClient()  # type: ignore[attr-defined]

    result = adapter.generate("hi", timeout_s=None)

    assert result == "ok"
    assert captured["max_tokens"] == 128
    assert captured["temperature"] == 0
    assert captured["stop"] == ["\n\n", "```", "<END>"]
    assert captured["extra"]["stream"] is False
    assert adapter._retry.timeout_s == 20.0
    assert captured["extra"]["top_p"] == 1
