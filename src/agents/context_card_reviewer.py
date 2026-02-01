import json
import re
from typing import List, Dict, Any
import httpx

from src.shared.config import OLLAMA_BASE, OLLAMA_REVIEWER_MODEL


def _extract_json(text: str):
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found")
    return json.loads(match.group(1))


def review_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prompt = {
        "role": "system",
        "content": (
            "You are a reviewer. If citations are missing or incorrect, fix them. "
            "Return JSON only with shape: {\"cards\":[...]}"
        ),
    }
    user_prompt = {
        "role": "user",
        "content": json.dumps({"cards": cards}, ensure_ascii=True),
    }
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": OLLAMA_REVIEWER_MODEL,
                "messages": [prompt, user_prompt],
                "temperature": 0,
                "stream": False,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response") or data.get("message", {}).get("content", "")
        parsed = _extract_json(text)
        reviewed = parsed["cards"] if isinstance(parsed, dict) else parsed
        return reviewed
    except Exception:
        return cards
