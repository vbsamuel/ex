from io import BytesIO
from minio import Minio
from minio.error import S3Error

from src.shared.config import MINIO_ENDPOINT, MINIO_BUCKET


def _endpoint_parts() -> tuple[str, bool]:
    if MINIO_ENDPOINT.startswith("http://"):
        return MINIO_ENDPOINT.replace("http://", ""), False
    if MINIO_ENDPOINT.startswith("https://"):
        return MINIO_ENDPOINT.replace("https://", ""), True
    return MINIO_ENDPOINT, False


class MinioArtifacts:
    def __init__(self, access_key: str = "minio", secret_key: str = "minio123") -> None:
        endpoint, secure = _endpoint_parts()
        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

    def ensure_bucket(self, bucket: str = MINIO_BUCKET) -> None:
        if not self._client.bucket_exists(bucket):
            self._client.make_bucket(bucket)

    def put_text(self, key: str, text: str, bucket: str = MINIO_BUCKET) -> str:
        self.ensure_bucket(bucket)
        data = text.encode("utf-8")
        self._client.put_object(bucket, key, BytesIO(data), length=len(data), content_type="text/plain")
        return f"{bucket}/{key}"
