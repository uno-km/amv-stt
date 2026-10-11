# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License

from termux_stt import create_engine


def test_engine_creation_default_auto():
    engine = create_engine("whisper", model="base")
    assert engine.config.device == "auto"
    info = engine.get_info()
    assert "device" in info
    assert info["device"] == "auto"


def test_engine_creation_explicit_cpu():
    engine = create_engine("whisper", model="base", device="cpu")
    assert engine.config.device == "cpu"
    info = engine.get_info()
    assert info["device"] == "cpu"
    if "backend_type" in info:
        assert info["backend_type"] == "cpu_neon"
        assert not info["is_gpu"]


def test_engine_creation_explicit_gpu_fail_fast():
    # Vulkan 미지원 호스트에서는 PlatformNotSupportedError 또는 정상 바인딩
    try:
        engine = create_engine("whisper", model="base", device="gpu")
        info = engine.get_info()
        assert info["device"] == "gpu"
    except Exception as e:
        assert "PlatformNotSupportedError" in type(e).__name__ or "GPU" in str(e)


def test_engine_registry_import_error_propagation():
    import pytest

    from termux_stt.engine import EngineRegistry

    # Simulate an engine import failure
    EngineRegistry._engines.pop("mock_broken", None)
    EngineRegistry._engine_import_errors["mock_broken"] = ImportError("No module named 'mock_broken_dep'")

    with pytest.raises(RuntimeError) as excinfo:
        EngineRegistry.get_engine("mock_broken")

    assert "is supported but failed to load due to an import/initialization error" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, ImportError)

    # Cleanup
    EngineRegistry._engine_import_errors.pop("mock_broken", None)


def test_engine_registry_unknown_engine_raises_value_error():
    import pytest

    from termux_stt.engine import EngineRegistry

    with pytest.raises(ValueError) as excinfo:
        EngineRegistry.get_engine("totally_non_existent_engine_xyz")

    assert "Unknown engine 'totally_non_existent_engine_xyz'" in str(excinfo.value)


def test_whisper_engine_diarize_method_success(monkeypatch):
    from termux_stt.export.result import DiarizedResult, Segment, TranscriptResult

    engine = create_engine("whisper", model="base")

    # Mock transcribe
    monkeypatch.setattr(
        engine,
        "transcribe",
        lambda audio_path, **kw: TranscriptResult(
            text="Whisper diarize test text",
            segments=[Segment(start=0.0, end=2.0, text="Whisper diarize test text")],
            language="ko",
            duration=2.0,
        ),
    )

    result = engine.diarize("dummy.wav", num_speakers=1)
    assert isinstance(result, DiarizedResult)
    assert len(result.segments) == 1
    assert result.segments[0].speaker == "Speaker_0"
    assert result.text == "Whisper diarize test text"


def test_whisper_engine_zero_silent_fallback(monkeypatch):
    import pytest
    from unittest.mock import MagicMock
    from termux_stt.engine.whisper_engine import WhisperEngine
    from termux_stt.engine.base import EngineConfig

    cfg = EngineConfig(engine="whisper", model="base", device="vulkan")
    engine = WhisperEngine.__new__(WhisperEngine)
    engine.config = cfg
    engine.device = "vulkan"
    engine.model = "base"
    engine.lang = "ko"
    engine.threads = 4
    engine.ctx = MagicMock()
    engine.ctx.is_gpu = True

    # Mock preprocess, ensure_model, binary path, and simulate missing -ngl support
    monkeypatch.setattr("termux_stt.audio.preprocessor.preprocess", lambda *a, **k: "test.wav")
    monkeypatch.setattr("termux_stt.models.hub.ModelHub.ensure_model", lambda *a, **k: "model.bin")
    monkeypatch.setattr(engine, "_get_binary_path", lambda: "/mock/whisper-cli")
    monkeypatch.setattr(engine, "_supports_ngl", lambda p: False)

    with pytest.raises(RuntimeError) as exc_info:
        engine.transcribe("test.wav")

    assert "[ZeroSilentFallback]" in str(exc_info.value)
    assert "does not support GPU offload (-ngl)" in str(exc_info.value)


