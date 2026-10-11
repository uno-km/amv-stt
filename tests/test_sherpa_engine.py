# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import pytest

from termux_stt import create_engine
from termux_stt.engine.sherpa_engine import SherpaEngine


def test_sherpa_engine_creation():
    engine = create_engine("sherpa", model="zipformer-ko", lang="ko")
    assert isinstance(engine, SherpaEngine)
    assert engine.model_name == "zipformer-ko"
    assert engine.config.language == "ko"


def test_sherpa_binary_missing_raises(monkeypatch):
    engine = create_engine("sherpa", model="zipformer-ko")

    # Mock preprocess and ModelHub to return valid paths without network requests
    monkeypatch.setattr("termux_stt.audio.preprocessor.preprocess", lambda p, **kw: p)
    monkeypatch.setattr("termux_stt.models.hub.ModelHub.ensure_model", lambda e, m: "/mock/model/dir")
    monkeypatch.setattr(engine, "_find_binary", lambda: None)

    # Calling transcribe without sherpa-onnx binary installed raises RuntimeError
    with pytest.raises(RuntimeError) as excinfo:
        engine.transcribe("valid_mock.wav")
    assert "not found" in str(excinfo.value) or "sherpa-onnx" in str(excinfo.value)
