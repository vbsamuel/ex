import json
import re
from typing import List, Dict, Any
import httpx

from src.shared.config import OLLAMA_BASE, OLLAMA_WRITER_MODEL


def _extract_json(text: str):
    match = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON found")
    return json.loads(match.group(1))


def _fallback_cards(evidence_units: List[Dict[str, Any]], min_cards: int) -> List[Dict[str, Any]]:
    cards = []
    for idx, eu in enumerate(evidence_units[:min_cards]):
        cards.append(
            {
                "title": f"Evidence {idx+1}",
                "summary": eu["text"],
                "key_points": [eu["text"]],
                "citations": [
                    {
                        "key_point_index": 0,
                        "evidence_unit_id": eu["id"],
                        "start_ms": eu["start_ms"],
                        "end_ms": eu["end_ms"],
                    }
                ],
            }
        )
    return cards


def generate_cards(evidence_units: List[Dict[str, Any]], min_cards: int = 2) -> List[Dict[str, Any]]:
    prompt = {
        "role": "system",
        "content": (
            "You produce JSON only. Create context cards from evidence units. "
            "Each card must include title, summary, key_points (array of strings), "
            "and citations (array of objects with key_point_index, evidence_unit_id, start_ms, end_ms). "
            "Every key point must have at least one citation."
        ),
    }
    evidence_blob = json.dumps(evidence_units, ensure_ascii=True)
    user_prompt = {
        "role": "user",
        "content": (
            "Generate at least 2 context cards from these evidence units. "
            "Return JSON with shape: {\"cards\":[...]} where cards are objects as specified.\n" + evidence_blob
        ),
    }
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": OLLAMA_WRITER_MODEL,
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
        cards = parsed["cards"] if isinstance(parsed, dict) else parsed
        if len(cards) < min_cards:
            return _fallback_cards(evidence_units, min_cards)
        return cards
    except Exception:
        return _fallback_cards(evidence_units, min_cards)
