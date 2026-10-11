# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License

import pytest

from termux_stt.models.hub import ModelHub
from termux_stt.models.registry import MODEL_REGISTRY, get_default_model, get_model_info


def test_model_registry_completeness():
    assert "whisper" in MODEL_REGISTRY
    assert "tiny" in MODEL_REGISTRY["whisper"]
    assert "large-v3-turbo" in MODEL_REGISTRY["whisper"]
    assert "sherpa" in MODEL_REGISTRY
    assert "3dspeaker-campplus" in MODEL_REGISTRY["sherpa"]
    assert "pyannote-segmentation-3-0" in MODEL_REGISTRY["sherpa"]

def test_get_model_info():
    info = get_model_info("whisper", "tiny")
    assert "url" in info
    assert "size" in info
    assert info["size"] == "75MB"

def test_get_default_model():
    assert get_default_model("whisper") == "small"
    assert get_default_model("sherpa") == "sensevoice-small-int8"

def test_model_typo_fuzzy_recommendation():
    """Verify that an unknown model typo raises ValueError with close matches and available model list."""
    with pytest.raises(ValueError) as excinfo:
        ModelHub.ensure_model("whisper", "tniyy")

    err_msg = str(excinfo.value)
    assert "Model 'tniyy' is not recognized for engine 'whisper'" in err_msg
    assert "Did you mean:" in err_msg
    assert "tiny" in err_msg
    assert "Available models for 'whisper':" in err_msg
    assert "large-v3-turbo" in err_msg


def test_verify_integrity_checksum(tmp_path):
    import hashlib
    dummy_file = tmp_path / "model.bin"
    content = b"whisper_model_data_12345"
    dummy_file.write_bytes(content)

    correct_sha = hashlib.sha256(content).hexdigest()
    assert ModelHub.verify_integrity(str(dummy_file), correct_sha) is True
    assert ModelHub.verify_integrity(str(dummy_file), "wrong_checksum") is False


def test_ensure_model_interactive_already_installed(monkeypatch):
    monkeypatch.setattr(ModelHub, "check_model_installed", lambda eng, mod: True)
    assert ModelHub.ensure_model_interactive("whisper", "small") is True


def test_ensure_model_interactive_non_tty_auto_download(monkeypatch):
    called = []
    monkeypatch.setattr(ModelHub, "check_model_installed", lambda eng, mod: False)
    monkeypatch.setattr(ModelHub, "ensure_model", lambda eng, mod: called.append((eng, mod)))
    import sys
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)

    res = ModelHub.ensure_model_interactive("whisper", "small")
    assert res is True
    assert called == [("whisper", "small")]

