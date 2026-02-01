import asyncio
import json
import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from src.shared.storage_pg import PgStore
from src.shared.kafka_producer import KafkaProducer
from src.shared.config import IEX_PROFILE
from src.agents.youtube_fetch import fetch_metadata
from src.agents.embedding_generator import embed_text

app = FastAPI()
store = PgStore()
producer = KafkaProducer()


@app.on_event("startup")
async def _startup():
    await store.connect()


@app.on_event("shutdown")
async def _shutdown():
    await store.close()


@app.get("/api/health")
async def health():
    return {"status": "ok", "profile": IEX_PROFILE}


@app.post("/api/run")
async def run_episode(payload: dict[str, Any]):
    youtube_url = payload.get("youtube_url")
    if not youtube_url:
        return JSONResponse({"error": "youtube_url required"}, status_code=400)

    meta = fetch_metadata(youtube_url)
    source_id = uuid.uuid4()
    episode_id = uuid.uuid4()

    await store.execute(
        "INSERT INTO core.sources (id, youtube_url, title, channel) VALUES ($1, $2, $3, $4)",
        source_id,
        meta.get("webpage_url") or youtube_url,
        meta.get("title"),
        meta.get("channel"),
    )
    await store.execute(
        "INSERT INTO core.episodes (id, source_id, status) VALUES ($1, $2, 'PENDING')",
        episode_id,
        source_id,
    )

    producer.send(
        "events.steps.requested.v1",
        {
            "episode_id": str(episode_id),
            "step": "episode.start",
            "youtube_url": youtube_url,
            "requested_at_ms": int(asyncio.get_event_loop().time() * 1000),
        },
    )

    return {"episode_id": str(episode_id)}


@app.get("/api/episode/{episode_id}")
async def episode_status(episode_id: str):
    row = await store.fetchrow("SELECT status FROM core.episodes WHERE id=$1", uuid.UUID(episode_id))
    status = row["status"] if row else "UNKNOWN"
    steps = await store.fetch(
        "SELECT step_name, status FROM core.episode_steps WHERE episode_id=$1 ORDER BY started_at NULLS LAST",
        uuid.UUID(episode_id),
    )
    return {
        "episode_id": episode_id,
        "status": status,
        "steps": [{"step": r["step_name"], "status": r["status"]} for r in steps],
    }


@app.get("/api/query")
async def query(q: str):
    vec = embed_text(q)
    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    rows = await store.fetch(
        """
        SELECT cc.id, cc.title, cc.summary, cc.key_points, cc.citations
        FROM core.context_cards cc
        JOIN core.embeddings e ON e.object_id = cc.id
        WHERE cc.status='VERIFIED'
        ORDER BY e.embedding <=> $1::vector
        LIMIT 5
        """,
        vec_str,
    )
    cards = []
    for r in rows:
        cards.append(
            {
                "id": str(r["id"]),
                "title": r["title"],
                "summary": r["summary"],
                "key_points": r["key_points"],
                "citations": r["citations"],
            }
        )
    return {"cards": cards}


@app.websocket("/ws/{episode_id}")
async def ws_status(ws: WebSocket, episode_id: str):
    await ws.accept()
    try:
        while True:
            row = await store.fetchrow("SELECT status FROM core.episodes WHERE id=$1", uuid.UUID(episode_id))
            status = row["status"] if row else "UNKNOWN"
            steps = await store.fetch(
                "SELECT step_name, status FROM core.episode_steps WHERE episode_id=$1 ORDER BY started_at NULLS LAST",
                uuid.UUID(episode_id),
            )
            payload = {
                "episode_id": episode_id,
                "status": status,
                "steps": [{"step": r["step_name"], "status": r["status"]} for r in steps],
            }
            await ws.send_text(json.dumps(payload, ensure_ascii=True))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        return


@app.get("/")
async def ui():
    html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>IE-X Demo</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    #cards { margin-top: 20px; }
    .card { border: 1px solid #ddd; padding: 12px; margin-bottom: 12px; }
    .status { margin-top: 10px; font-family: monospace; white-space: pre; }
  </style>
</head>
<body>
  <h1>IE-X Demo</h1>
  <input id=\"url\" size=\"80\" placeholder=\"YouTube URL\" />
  <button id=\"run\">Run</button>
  <div class=\"status\" id=\"status\"></div>
  <div>
    <input id=\"query\" size=\"60\" placeholder=\"Query\" />
    <button id=\"search\">Search</button>
  </div>
  <div id=\"cards\"></div>
<script>
let episodeId = null;
let ws = null;

document.getElementById('run').onclick = async () => {
  const url = document.getElementById('url').value;
  const res = await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({youtube_url: url})});
  const data = await res.json();
  episodeId = data.episode_id;
  document.getElementById('status').textContent = 'Episode ' + episodeId + ' started';
  if (ws) ws.close();
  ws = new WebSocket(`ws://${location.host}/ws/${episodeId}`);
  ws.onmessage = (evt) => {
    const payload = JSON.parse(evt.data);
    document.getElementById('status').textContent = JSON.stringify(payload, null, 2);
  };
};

document.getElementById('search').onclick = async () => {
  const q = document.getElementById('query').value;
  const res = await fetch(`/api/query?q=${encodeURIComponent(q)}`);
  const data = await res.json();
  const cards = document.getElementById('cards');
  cards.innerHTML = '';
  for (const c of data.cards) {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `<h3>${c.title}</h3><p>${c.summary}</p><pre>${JSON.stringify(c.citations, null, 2)}</pre>`;
    cards.appendChild(div);
  }
};
</script>
</body>
</html>
"""
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.services.api_gateway:app", host="0.0.0.0", port=8000, reload=False)
