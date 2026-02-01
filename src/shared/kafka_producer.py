import json
from confluent_kafka import Producer
from src.shared.config import KAFKA_BOOTSTRAP


class KafkaProducer:
    def __init__(self, bootstrap: str = KAFKA_BOOTSTRAP) -> None:
        self._producer = Producer({"bootstrap.servers": bootstrap})

    def send(self, topic: str, value: dict) -> None:
        payload = json.dumps(value, ensure_ascii=True).encode("utf-8")
        self._producer.produce(topic, payload)
        self._producer.flush(5)
