import redis
from src.shared.config import DRAGONFLY_REDIS, CACHE_PREFIX


class Cache:
    def __init__(self, url: str = DRAGONFLY_REDIS, prefix: str = CACHE_PREFIX) -> None:
        self._client = redis.Redis.from_url(url)
        self._prefix = prefix

    def key(self, name: str) -> str:
        return f"{self._prefix}:{name}"

    def get(self, name: str):
        return self._client.get(self.key(name))

    def set(self, name: str, value: str, ex: int | None = None) -> None:
        self._client.set(self.key(name), value, ex=ex)
