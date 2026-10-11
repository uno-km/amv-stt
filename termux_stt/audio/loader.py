# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Audio loading module for termux-stt.
Supports multiple formats (wav, mp3, m4a, flac, ogg, opus, webm).
"""

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict

__all__ = ["AudioData", "load_audio", "is_supported_format", "get_audio_info"]

SUPPORTED_FORMATS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".webm"}

@dataclass
class AudioData:
    samples: bytes
    sample_rate: int
    channels: int
    duration: float
    format: str

def is_supported_format(path: str) -> bool:
    """Check if the given file has a supported audio format extension."""
    _, ext = os.path.splitext(path)
    return ext.lower() in SUPPORTED_FORMATS

def get_audio_info(path: str) -> Dict[str, Any]:
    """Get audio metadata using pure Python wave module first, then ffprobe."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    # 1. Fast Pure Python WAV parser (Zero external dependencies)
    try:
        import wave
        with wave.open(path, "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / float(sample_rate) if sample_rate > 0 else 0.0
            return {
                "format": {"format_name": "wav", "duration": duration},
                "streams": [{"codec_type": "audio", "codec_name": "pcm_s16le", "sample_rate": sample_rate, "channels": channels, "duration": duration}],
            }
    except (wave.Error, EOFError) as _wave_err:
        # Non-WAV audio format (e.g. mp3, m4a, flac, ogg); proceed to ffprobe metadata parser
        _ = _wave_err

    # 2. ffprobe fallback for non-WAV formats
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to probe audio file: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}")


def load_audio(path: str) -> AudioData:
    """Load audio file and return AudioData."""
    if not is_supported_format(path):
        raise ValueError(f"Unsupported format for {path}")

    info = get_audio_info(path)
    # Parse info to get basic details (some streams might vary)
    streams = info.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not audio_stream:
        raise ValueError("No audio stream found in file.")

    sample_rate = int(audio_stream.get("sample_rate", 16000))
    channels = int(audio_stream.get("channels", 1))

    # Try to get duration
    duration = float(info.get("format", {}).get("duration", 0.0))
    if not duration and audio_stream.get("duration"):
        duration = float(audio_stream["duration"])

    format_name = info.get("format", {}).get("format_name", "unknown")

    # Read binary data with OOM protection (Max 100MB)
    max_bytes = 100 * 1024 * 1024
    file_size = os.path.getsize(path)
    if file_size > max_bytes:
        raise ValueError(
            f"Audio file '{path}' ({file_size / (1024*1024):.1f}MB) exceeds in-memory limit (100MB). "
            "Use stream_file() or engine.transcribe() to process large audio safely without OOM."
        )

    with open(path, "rb") as f:
        samples = f.read()

    return AudioData(
        samples=samples,
        sample_rate=sample_rate,
        channels=channels,
        duration=duration,
        format=format_name
    )
