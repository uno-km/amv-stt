# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import os
import shutil
import subprocess
import tempfile
import wave
from typing import Optional

__all__ = ["preprocess", "ensure_wav_format", "validate_audio"]


import logging

logger = logging.getLogger(__name__)


def validate_audio(path: str) -> bool:
    """
    Validate audio size and existence.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: '{path}'")
    size = os.path.getsize(path)
    if size < 44:  # At least smaller than a standard WAV header
        raise ValueError(f"Audio file '{path}' is too small ({size} bytes) for valid audio.")
    return True


def _check_pure_wav(path: str, target_sr: int = 16000, target_channels: int = 1) -> bool:
    """Check if audio is already target WAV format using pure Python standard library."""
    try:
        with wave.open(path, "rb") as wf:
            return (
                wf.getnchannels() == target_channels
                and wf.getsampwidth() == 2  # 16-bit PCM
                and wf.getframerate() == target_sr
            )
    except (wave.Error, EOFError) as e:
        logger.debug("File '%s' is not standard PCM WAV: %s", path, e)
        return False
    except OSError as e:
        logger.warning("I/O error reading audio file '%s': %s", path, e)
        return False


def preprocess(
    input_path: str,
    output_path: Optional[str] = None,
    target_sr: int = 16000,
    force_mono: bool = True,
) -> str:
    """
    Convert audio to 16kHz, 1 channel, PCM s16le WAV.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Fast path: already 16kHz Mono 16-bit PCM WAV
    channels_int = 1 if force_mono else 2
    if _check_pure_wav(input_path, target_sr, channels_int) and output_path is None:
        return input_path

    if output_path is None:
        fd, output_path = tempfile.mkstemp(suffix=".wav", prefix="termux_stt_")
        os.close(fd)

    channels = "1" if force_mono else "2"
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ac", channels,
        "-ar", str(target_sr),
        "-c:a", "pcm_s16le",
        "-v", "quiet",
        output_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except subprocess.CalledProcessError as e:
        # Attempt auto-repair on Termux if libbluray linker error is suspected
        if shutil.which("pkg"):
            try:
                subprocess.run(["pkg", "install", "-y", "libbluray", "libxml2"], check=False, capture_output=True)
                subprocess.run(cmd, check=True, capture_output=True)
                return output_path
            except Exception as repair_err:
                logger.debug("Termux ffmpeg package auto-repair failed: %s", repair_err)

        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError as rm_err:
                logger.debug("Failed to remove temporary output '%s': %s", output_path, rm_err)
        err_msg = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        raise RuntimeError(f"FFmpeg conversion failed: {err_msg}")


def ensure_wav_format(path: str) -> str:
    """
    Check if the file is already 16kHz mono pcm_s16le wav.
    If not, convert it and return the new temp path.
    """
    # 1. Pure Python wave check (0 subprocess, 0 ffmpeg dependency)
    if _check_pure_wav(path, 16000, 1):
        return path

    # 2. ffprobe check if available
    try:
        import json
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        streams = info.get("streams", [])
        if streams:
            stream = streams[0]
            if (
                stream.get("codec_name") == "pcm_s16le"
                and stream.get("channels") == 1
                and str(stream.get("sample_rate")) == "16000"
            ):
                return path
    except Exception as probe_err:
        logger.debug("ffprobe stream verification skipped: %s", probe_err)

    return preprocess(path)
