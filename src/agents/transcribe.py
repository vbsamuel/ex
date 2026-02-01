import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List


@dataclass
class EvidenceSegment:
    start_ms: int
    end_ms: int
    text: str


_TS_RE = re.compile(r"(\d+):(\d+):(\d+)\.(\d+)")


def _ts_to_ms(ts: str) -> int:
    m = _TS_RE.match(ts)
    if not m:
        return 0
    h, mnt, s, ms = map(int, m.groups())
    return ((h * 60 + mnt) * 60 + s) * 1000 + ms


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def download_captions_vtt(url: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-auto-subs",
            "--sub-format",
            "vtt",
            "--skip-download",
            url,
        ]
        subprocess.run(cmd, cwd=tmpdir, check=True)
        vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
        if not vtt_files:
            raise RuntimeError("No captions VTT available for URL")
        vtt_path = os.path.join(tmpdir, vtt_files[0])
        with open(vtt_path, "r", encoding="utf-8") as f:
            return f.read()


def parse_vtt(vtt_text: str) -> List[EvidenceSegment]:
    segments: List[EvidenceSegment] = []
    lines = vtt_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            start_ts, end_ts = [t.strip() for t in line.split("-->")]
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() != "":
                text_lines.append(lines[i].strip())
                i += 1
            text = _clean_text(" ".join(text_lines))
            if text:
                segments.append(
                    EvidenceSegment(
                        start_ms=_ts_to_ms(start_ts),
                        end_ms=_ts_to_ms(end_ts),
                        text=text,
                    )
                )
        else:
            i += 1
    return segments
