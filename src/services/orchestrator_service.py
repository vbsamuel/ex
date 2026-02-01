import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, Any

from src.shared.storage_pg import PgStore
from src.shared.kafka_consumer import KafkaConsumer
from src.shared.kafka_producer import KafkaProducer
from src.agents.transcribe import download_captions_vtt, parse_vtt
from src.agents.context_card_writer import generate_cards
from src.agents.context_card_reviewer import review_cards
from src.agents.embedding_generator import embed_text
from src.tools.grounding_verifier import verify_card
from src.shared.artifact_minio import MinioArtifacts

STEP_ORDER = ["transcribe", "context_cards", "embeddings"]


def _now() -> datetime:
    return datetime.utcnow()


def _vec_str(vec: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vec) + "]"


async def _upsert_step(store: PgStore, episode_id: uuid.UUID, step: str, status: str, error: str | None = None) -> None:
    await store.execute(
        """
        INSERT INTO core.episode_steps (id, episode_id, step_name, status, started_at, completed_at, error)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        uuid.uuid4(),
        episode_id,
        step,
        status,
        _now() if status == "RUNNING" else None,
        _now() if status in ("COMPLETED", "FAILED") else None,
        error,
    )


async def _emit_step_requested(producer: KafkaProducer, episode_id: str, step: str, youtube_url: str | None = None) -> None:
    producer.send(
        "events.steps.requested.v1",
        {
            "episode_id": episode_id,
            "step": step,
            "youtube_url": youtube_url,
            "requested_at_ms": int(time.time() * 1000),
        },
    )


async def _emit_step_completed(producer: KafkaProducer, episode_id: str, step: str, status: str, message: str | None = None) -> None:
    producer.send(
        "events.steps.completed.v1",
        {
            "episode_id": episode_id,
            "step": step,
            "status": status,
            "message": message or "",
            "completed_at_ms": int(time.time() * 1000),
        },
    )


async def handle_transcribe(store: PgStore, episode_id: uuid.UUID, youtube_url: str) -> None:
    vtt_text = download_captions_vtt(youtube_url)
    segments = parse_vtt(vtt_text)
    if not segments:
        raise RuntimeError("No caption segments parsed")

    artifacts = MinioArtifacts()
    key = f"{episode_id}/captions.vtt"
    artifacts.put_text(key, vtt_text)
    await store.execute(
        "INSERT INTO core.artifacts (id, episode_id, kind, uri) VALUES ($1, $2, $3, $4)",
        uuid.uuid4(),
        episode_id,
        "captions.vtt",
        key,
    )

    rows = [
        (
            uuid.uuid4(),
            episode_id,
            youtube_url,
            seg.start_ms,
            seg.end_ms,
            seg.text,
        )
        for seg in segments
    ]
    await store.executemany(
        "INSERT INTO core.evidence_units (id, episode_id, source_url, start_ms, end_ms, text) VALUES ($1, $2, $3, $4, $5, $6)",
        rows,
    )


async def handle_context_cards(store: PgStore, episode_id: uuid.UUID) -> None:
    evidence = await store.fetch(
        "SELECT id, start_ms, end_ms, text FROM core.evidence_units WHERE episode_id=$1 ORDER BY start_ms",
        episode_id,
    )
    evidence_units = [
        {
            "id": str(r["id"]),
            "start_ms": r["start_ms"],
            "end_ms": r["end_ms"],
            "text": r["text"],
        }
        for r in evidence
    ]
    if not evidence_units:
        raise RuntimeError("No evidence units found")

    cards = generate_cards(evidence_units, min_cards=2)
    cards = review_cards(cards)

    evidence_map = {e["id"]: e for e in evidence_units}
    verified_count = 0
    for card in cards:
        status = "VERIFIED" if verify_card(card, evidence_map) else "REJECTED"
        if status == "VERIFIED":
            verified_count += 1
        await store.execute(
            """
            INSERT INTO core.context_cards (id, episode_id, title, summary, key_points, citations, status)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
            """,
            uuid.uuid4(),
            episode_id,
            card.get("title") or "Untitled",
            card.get("summary") or "",
            json.dumps(card.get("key_points") or [], ensure_ascii=True),
            json.dumps(card.get("citations") or [], ensure_ascii=True),
            status,
        )

    if verified_count < 2:
        raise RuntimeError("Verified context cards < 2")


async def handle_embeddings(store: PgStore, episode_id: uuid.UUID) -> None:
    cards = await store.fetch(
        "SELECT id, summary FROM core.context_cards WHERE episode_id=$1 AND status='VERIFIED'",
        episode_id,
    )
    if not cards:
        raise RuntimeError("No verified context cards")

    for card in cards:
        vec = embed_text(card["summary"])
        vec_str = _vec_str(vec)
        await store.execute(
            "INSERT INTO core.embeddings (id, episode_id, object_type, object_id, embedding) VALUES ($1, $2, $3, $4, $5::vector)",
            uuid.uuid4(),
            episode_id,
            "context_card",
            card["id"],
            vec_str,
        )


async def handle_step(msg: Dict[str, Any], store: PgStore, producer: KafkaProducer) -> None:
    step = msg.get("step")
    episode_id = uuid.UUID(msg["episode_id"])
    youtube_url = msg.get("youtube_url")

    if step == "episode.start":
        await store.execute("UPDATE core.episodes SET status='RUNNING' WHERE id=$1", episode_id)
        await _emit_step_requested(producer, msg["episode_id"], STEP_ORDER[0], youtube_url)
        return

    await _upsert_step(store, episode_id, step, "RUNNING")
    try:
        if step == "transcribe":
            if not youtube_url:
                row = await store.fetchrow(
                    "SELECT s.youtube_url FROM core.sources s JOIN core.episodes e ON e.source_id=s.id WHERE e.id=$1",
                    episode_id,
                )
                youtube_url = row["youtube_url"] if row else None
            if not youtube_url:
                raise RuntimeError("missing youtube_url")
            await handle_transcribe(store, episode_id, youtube_url)
        elif step == "context_cards":
            await handle_context_cards(store, episode_id)
        elif step == "embeddings":
            await handle_embeddings(store, episode_id)
        else:
            raise RuntimeError(f"unknown step {step}")

        await _upsert_step(store, episode_id, step, "COMPLETED")
        await _emit_step_completed(producer, msg["episode_id"], step, "COMPLETED")

        if step in STEP_ORDER:
            idx = STEP_ORDER.index(step)
            if idx + 1 < len(STEP_ORDER):
                await _emit_step_requested(producer, msg["episode_id"], STEP_ORDER[idx + 1])
            else:
                await store.execute("UPDATE core.episodes SET status='COMPLETED' WHERE id=$1", episode_id)
    except Exception as exc:
        await _upsert_step(store, episode_id, step, "FAILED", error=str(exc))
        await _emit_step_completed(producer, msg["episode_id"], step, "FAILED", message=str(exc))
        await store.execute("UPDATE core.episodes SET status='FAILED' WHERE id=$1", episode_id)


async def run() -> None:
    store = PgStore()
    await store.connect()
    producer = KafkaProducer()
    consumer = KafkaConsumer(group_id="iex-demo-orchestrator", topics=["events.steps.requested.v1"])

    try:
        while True:
            msg = await asyncio.to_thread(consumer.poll, 1.0)
            if not msg:
                continue
            await handle_step(msg, store, producer)
    finally:
        consumer.close()
        await store.close()


if __name__ == "__main__":
    asyncio.run(run())
