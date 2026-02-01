import json
from confluent_kafka import Consumer
from src.shared.config import KAFKA_BOOTSTRAP


class KafkaConsumer:
    def __init__(self, group_id: str, topics: list[str], bootstrap: str = KAFKA_BOOTSTRAP) -> None:
        self._consumer = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": group_id,
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        self._consumer.subscribe(topics)

    def poll(self, timeout: float = 1.0):
        msg = self._consumer.poll(timeout)
        if msg is None:
            return None
        if msg.error():
            return None
        try:
            return json.loads(msg.value().decode("utf-8"))
        except Exception:
            return None

    def close(self) -> None:
        self._consumer.close()
