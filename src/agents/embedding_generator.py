import httpx
from src.shared.config import OLLAMA_BASE, OLLAMA_EMBED_MODEL


def embed_text(text: str) -> list[float]:
    resp = httpx.post(
        f"{OLLAMA_BASE}/api/embeddings",
        json={"model": OLLAMA_EMBED_MODEL, "prompt": text},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    vec = data.get("embedding")
    if vec is None:
        raise RuntimeError("No embedding returned")
    if len(vec) != 768:
        raise RuntimeError(f"Embedding length {len(vec)} != 768")
    return vec
