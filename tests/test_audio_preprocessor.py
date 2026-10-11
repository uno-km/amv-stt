# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import os
import struct
import wave

import pytest

from termux_stt.audio.loader import get_audio_info, is_supported_format
from termux_stt.audio.preprocessor import _check_pure_wav, ensure_wav_format, validate_audio


def _create_synthetic_wav(path: str, sr: int = 16000, channels: int = 1, duration_sec: float = 1.0):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        n_samples = int(sr * duration_sec)
        # Generate 440Hz sine-like int16 sequence
        data = bytearray()
        for i in range(n_samples):
            val = int(10000 * (1 if (i // 20) % 2 == 0 else -1))
            data.extend(struct.pack("<h", val))
            if channels == 2:
                data.extend(struct.pack("<h", val))
        wf.writeframes(data)


def test_supported_formats():
    assert is_supported_format("test.wav")
    assert is_supported_format("audio.MP3")
    assert is_supported_format("track.m4a")
    assert is_supported_format("voice.ogg")
    assert is_supported_format("speech.flac")
    assert not is_supported_format("document.pdf")
    assert not is_supported_format("image.png")


def test_validate_audio(tmp_path):
    # Non-existent file
    with pytest.raises(FileNotFoundError):
        validate_audio(str(tmp_path / "non_existent.wav"))

    # Too small file
    small_file = tmp_path / "small.wav"
    small_file.write_bytes(b"RIFF1234")
    with pytest.raises(ValueError) as exc:
        validate_audio(str(small_file))
    assert "too small" in str(exc.value)

    # Valid synthetic WAV
    valid_wav = tmp_path / "valid.wav"
    _create_synthetic_wav(str(valid_wav), 16000, 1, 0.5)
    assert validate_audio(str(valid_wav)) is True


def test_pure_wav_check_and_info(tmp_path):
    wav_16k_mono = str(tmp_path / "mono_16k.wav")
    _create_synthetic_wav(wav_16k_mono, 16000, 1, 1.0)
    assert _check_pure_wav(wav_16k_mono, 16000, 1) is True

    info = get_audio_info(wav_16k_mono)
    assert info["format"]["format_name"] == "wav"
    assert abs(info["format"]["duration"] - 1.0) < 0.05

    wav_44k_stereo = str(tmp_path / "stereo_44k.wav")
    _create_synthetic_wav(wav_44k_stereo, 44100, 2, 0.5)
    assert _check_pure_wav(wav_44k_stereo, 16000, 1) is False


def test_ensure_wav_format_passthrough(tmp_path):
    wav_16k_mono = str(tmp_path / "mono_16k.wav")
    _create_synthetic_wav(wav_16k_mono, 16000, 1, 1.0)
    # If already 16kHz mono, ensure_wav_format must return exact same path without reprocessing
    result_path = ensure_wav_format(wav_16k_mono)
    assert os.path.abspath(result_path) == os.path.abspath(wav_16k_mono)


def test_load_audio_and_mic_fail_fast(tmp_path):
    from termux_stt.audio.loader import load_audio
    from termux_stt.audio.mic import MicCapture

    wav_16k_mono = str(tmp_path / "mono_16k.wav")
    _create_synthetic_wav(wav_16k_mono, 16000, 1, 0.5)

    audio_data = load_audio(wav_16k_mono)
    assert audio_data.sample_rate == 16000
    assert audio_data.channels == 1
    assert len(audio_data.samples) > 0

    # Mic without device should fail fast rather than emitting fake silent bytes
    mic = MicCapture()
    with pytest.raises(RuntimeError) as excinfo:
        # Request short stream
        for _ in mic.stream(duration=0.1, chunk_sec=0.1):
            pass
    assert "Microphone capture failed" in str(excinfo.value)


def test_split_by_speech_ffmpeg_failure_raises_and_cleans_up(tmp_path):
    import subprocess
    from unittest.mock import patch

    from termux_stt.audio.vad import VADResult, split_by_speech

    wav_16k_mono = str(tmp_path / "mono_16k.wav")
    _create_synthetic_wav(wav_16k_mono, 16000, 1, 1.0)

    vad_res = VADResult(segments=[(0.0, 0.5), (0.5, 1.0)], speech_ratio=1.0)

    # Mock subprocess.run to fail on second segment
    call_count = 0

    def mock_subp_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise subprocess.CalledProcessError(1, cmd, stderr="Invalid audio stream slice")
        # First segment succeeds: create dummy file
        out_file = cmd[-1]
        with open(out_file, "wb") as f:
            f.write(b"dummy")
        return subprocess.CompletedProcess(cmd, 0)

    with patch("subprocess.run", side_effect=mock_subp_run):
        with pytest.raises(RuntimeError) as excinfo:
            split_by_speech(wav_16k_mono, vad_res)

    assert "FFmpeg segmentation failed on segment 1" in str(excinfo.value)
    assert "Invalid audio stream slice" in str(excinfo.value)
