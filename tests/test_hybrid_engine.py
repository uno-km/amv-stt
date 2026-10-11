# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import os
import tempfile
import wave
import pytest
from termux_stt import create_engine
from termux_stt.engine.hybrid_engine import HybridEngine
from termux_stt.export.result import Segment, TranscriptResult


def test_hybrid_engine_creation():
    engine = create_engine("hybrid", model="base", lang="ko", num_speakers=2)
    assert isinstance(engine, HybridEngine)
    assert engine.config.lang == "ko"
    assert engine.config.num_speakers == 2


def test_hybrid_diarize_mocked_neural_components(monkeypatch):
    engine = create_engine("hybrid", model="base", lang="ko", num_speakers=2)

    # Mock whisper transcribe
    monkeypatch.setattr(
        engine._whisper,
        "transcribe",
        lambda wav_path, **kw: TranscriptResult(
            text="Hello world test speech",
            segments=[
                Segment(start=0.0, end=2.0, text="Hello world"),
                Segment(start=2.5, end=4.0, text="test speech"),
            ],
            language="ko",
            duration=4.0,
        ),
    )

    # Mock neural diarizer intervals: [(start, end, speaker_id)]
    monkeypatch.setattr(
        engine._diarizer,
        "diarize_audio",
        lambda wav_path, num_speakers=2: [
            (0.0, 2.0, 0),
            (2.5, 4.0, 1),
        ],
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)
        tmp_wav = tmp.name

    try:
        res = engine.diarize(tmp_wav, num_speakers=2)
        assert len(res.segments) == 2
        assert res.segments[0].speaker == "Speaker_0"
        assert res.segments[1].speaker == "Speaker_1"
        assert "Hello world" in res.text
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)


def test_hybrid_diarize_failure_raises_when_fallback_disabled(monkeypatch):
    engine = create_engine("hybrid", model="base", lang="ko", num_speakers=2)

    monkeypatch.setattr(
        engine._diarizer,
        "diarize_audio",
        lambda wav_path, num_speakers=2: (_ for _ in ()).throw(RuntimeError("PyAnnote model missing")),
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)
        tmp_wav = tmp.name

    try:
        with pytest.raises(RuntimeError) as excinfo:
            engine.diarize(tmp_wav, num_speakers=2, allow_fallback=False)
        assert "Neural speaker diarization failed" in str(excinfo.value)
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)


def test_hybrid_diarize_failure_fallback_unknown(monkeypatch):
    engine = create_engine("hybrid", model="base", lang="ko", num_speakers=2)

    monkeypatch.setattr(
        engine._diarizer,
        "diarize_audio",
        lambda wav_path, num_speakers=2: (_ for _ in ()).throw(RuntimeError("model missing")),
    )
    monkeypatch.setattr(
        engine._whisper,
        "transcribe",
        lambda wav_path, **kw: TranscriptResult(
            text="Fallback test speech",
            segments=[Segment(start=0.0, end=2.0, text="Fallback test speech")],
            language="ko",
            duration=2.0,
        ),
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 32000)
        tmp_wav = tmp.name

    try:
        res = engine.diarize(tmp_wav, num_speakers=2, allow_fallback=True)
        assert len(res.segments) == 1
        assert res.segments[0].speaker == "Speaker_0" or res.segments[0].speaker == "Speaker_Unknown"
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
