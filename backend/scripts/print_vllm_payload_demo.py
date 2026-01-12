#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.rlm.services.run_pipeline import _build_compact_decision_messages  # type: ignore


def main() -> int:
    question = " ".join(sys.argv[1:]) or "What is this demo about?"
    evidence = [{"glimpses": [{"text": "demo evidence text " * 10}]}]
    messages = _build_compact_decision_messages(question, evidence)
    total_chars = sum(len(m["content"]) for m in messages)
    print(f"messages={len(messages)} total_chars={total_chars}")
    for idx, msg in enumerate(messages, start=1):
        content = msg["content"]
        print(f"{idx}. {msg['role']} len={len(content)} preview={content[:120].replace(chr(10),' ')}")
    payload = {
        "messages": messages,
        "max_tokens": 16,
        "temperature": 0,
        "stop": ["\\n", "\\n\\n", "```", "<END>"],
    }
    print("json_preview:", json.dumps(payload, ensure_ascii=False)[:240])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
