import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from typing import List

from faster_whisper import WhisperModel

from src.shared.config import ASR_MODEL


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


def _has_timing(vtt_text: str) -> bool:
    for line in vtt_text.splitlines():
        if "-->" in line:
            return True
    return False


def _try_download(tmpdir: str, args: list[str]) -> str | None:
    result = subprocess.run(args, cwd=tmpdir, capture_output=True, text=True)
    vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
    if not vtt_files:
        return None
    vtt_path = os.path.join(tmpdir, vtt_files[0])
    with open(vtt_path, "r", encoding="utf-8") as f:
        text = f.read()
    if not _has_timing(text):
        return None
    return text


def download_captions_vtt(url: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        auto_args = [
            "yt-dlp",
            "--write-auto-subs",
            "--sub-format",
            "vtt",
            "--skip-download",
            url,
        ]
        text = _try_download(tmpdir, auto_args)
        if text:
            return text

        manual_args = [
            "yt-dlp",
            "--write-subs",
            "--sub-langs",
            "en",
            "--sub-format",
            "vtt",
            "--skip-download",
            url,
        ]
        text = _try_download(tmpdir, manual_args)
        if text:
            return text

        raise RuntimeError("No captions VTT available for URL")


def _extract_audio(url: str, tmpdir: str) -> str:
    output_tmpl = os.path.join(tmpdir, "audio.%(ext)s")
    args = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "--output",
        output_tmpl,
        url,
    ]
    result = subprocess.run(args, cwd=tmpdir, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed rc={result.returncode}")
    wav_path = os.path.join(tmpdir, "audio.wav")
    if not os.path.exists(wav_path):
        raise RuntimeError("Audio file not created")
    return wav_path


def _transcribe_audio(url: str) -> List[EvidenceSegment]:
    with tempfile.TemporaryDirectory() as tmpdir:
        wav_path = _extract_audio(url, tmpdir)
        model = WhisperModel(ASR_MODEL, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(wav_path, language="en")
        out: List[EvidenceSegment] = []
        for seg in segments:
            text = _clean_text(seg.text)
            if not text:
                continue
            out.append(
                EvidenceSegment(
                    start_ms=int(seg.start * 1000),
                    end_ms=int(seg.end * 1000),
                    text=text,
                )
            )
        if not out:
            raise RuntimeError("Audio transcription produced no segments")
        return out


def get_evidence_segments(url: str) -> List[EvidenceSegment]:
    try:
        vtt = download_captions_vtt(url)
        segments = parse_vtt(vtt)
        if segments:
            return segments
    except Exception:
        pass
    return _transcribe_audio(url)


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
