import json
import subprocess


def fetch_metadata(url: str) -> dict:
    result = subprocess.run(
        ["yt-dlp", "--skip-download", "--dump-json", url],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout.strip())
    return {
        "title": data.get("title"),
        "channel": data.get("channel"),
        "id": data.get("id"),
        "webpage_url": data.get("webpage_url") or url,
    }
