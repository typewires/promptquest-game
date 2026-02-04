from __future__ import annotations

import json
from typing import Any

from openai import OpenAI


def summarize_with_openai(
    *,
    openai_api_key: str | None,
    model: str,
    prompt: str,
) -> dict[str, Any]:
    if not openai_api_key:
        return {"ok": False, "text": None, "data": None, "error": "OPENAI_API_KEY not set"}
    try:
        client = OpenAI(api_key=openai_api_key)
        resp = client.responses.create(model=model, input=prompt)
        text = (getattr(resp, "output_text", None) or "").strip()
        data = None
        try:
            data = json.loads(text)
        except Exception:
            data = None
        return {"ok": True, "text": text, "data": data, "error": None}
    except Exception as e:
        return {"ok": False, "text": None, "data": None, "error": str(e)}
