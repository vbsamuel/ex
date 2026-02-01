import os


def env(key: str, default: str) -> str:
    return os.environ.get(key, default)


IEX_PROFILE = env("IEX_PROFILE", "demo")

KAFKA_BOOTSTRAP = env("KAFKA_BOOTSTRAP", "localhost:9092")
SCHEMA_REGISTRY_URL = env("SCHEMA_REGISTRY_URL", "http://localhost:8081")
POSTGRES_DSN = env("POSTGRES_DSN", "postgresql://mini_brain:mini_brain_pw@localhost:5432/mini_brain")
MINIO_ENDPOINT = env("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_CONSOLE = env("MINIO_CONSOLE", "http://localhost:9001")
MINIO_BUCKET = env("MINIO_BUCKET", "mini-brain")
DRAGONFLY_REDIS = env("DRAGONFLY_REDIS", "redis://127.0.0.1:6379")
CACHE_PREFIX = env("CACHE_PREFIX", "mini-brain")

OLLAMA_BASE = env("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_WRITER_MODEL = env("OLLAMA_WRITER_MODEL", "gemma3:12b-it-qat")
OLLAMA_REVIEWER_MODEL = env("OLLAMA_REVIEWER_MODEL", "deepseek-coder-v2:16b")
OLLAMA_EMBED_MODEL = env("OLLAMA_EMBED_MODEL", "nomic-embed-text:latest")
ASR_MODEL = env("ASR_MODEL", "base")
