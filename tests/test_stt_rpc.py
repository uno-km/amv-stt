# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""Unit tests for distributed RPC and multi-node tensor splitting in termux-stt."""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from termux_stt.engine.base import EngineConfig
from termux_stt.engine.whisper_engine import WhisperEngine
from termux_stt.cli.main import _run_cli


def test_cli_stt_rpc_and_tensor_split_args(tmp_path):
    """Verify CLI parses --rpc and -ts flags for transcribe subcommand and forwards them."""
    dummy_wav = tmp_path / "test.wav"
    dummy_wav.write_bytes(b"RIFF" + b"\x00" * 36 + b"data" + b"\x00" * 16)

    with patch("termux_stt.cli.transcribe.create_engine") as mock_create, \
         patch("termux_stt.cli.transcribe.resolve_safe_output_path", return_value=str(tmp_path / "out.txt")):
        mock_eng = MagicMock()
        mock_res = MagicMock()
        mock_res.text = "Transcribed speech text"
        mock_eng.transcribe.return_value = mock_res
        mock_create.return_value = mock_eng

        with patch("sys.argv", [
            "termux-stt",
            "transcribe",
            str(dummy_wav),
            "--rpc", "192.168.0.220:50052,192.168.0.253:50052",
            "-ts", "50,50",
            "--engine", "whisper",
            "--device", "cpu",
        ]):
            _run_cli()

        assert mock_create.called
        kwargs = mock_create.call_args[1]
        assert kwargs["rpc"] == "192.168.0.220:50052,192.168.0.253:50052"
        assert kwargs["tensor_split"] == "50,50"


def test_whisper_engine_transcribe_injects_rpc(tmp_path):
    """Verify WhisperEngine.transcribe injects --rpc and --tensor-split into whisper-cli argv."""
    dummy_wav = tmp_path / "speech.wav"
    dummy_wav.write_bytes(b"RIFF" + b"\x00" * 36 + b"data" + b"\x00" * 16)
    dummy_model = tmp_path / "model.bin"
    dummy_model.write_bytes(b"GGML" + b"\x00" * 32)

    config = EngineConfig(
        model_name=str(dummy_model),
        language="ko",
        device="cpu",
        threads=4,
        extra={"rpc": "192.168.0.220:50052", "tensor_split": "60,40"}
    )

    engine = WhisperEngine(config)

    captured_cmd = []

    from termux_stt.platform.process_pool import SubprocessResult

    def fake_run_isolated(cmd, env=None, timeout_sec=None):
        captured_cmd.extend(cmd)
        return SubprocessResult(
            returncode=0,
            stdout='{"transcription": [{"offsets": {"from": 0, "to": 1000}, "text": "안녕"}]}',
            stderr="",
            duration_sec=0.1,
        )

    with patch.object(engine, "_get_binary_path", return_value=str(tmp_path / "whisper-cli")), \
         patch("termux_stt.engine.whisper_engine.verify_rpc_cluster_nodes"), \
         patch("termux_stt.audio.preprocessor.ensure_wav_format", return_value=str(dummy_wav)), \
         patch("termux_stt.platform.process_pool.run_isolated", side_effect=fake_run_isolated):

        res = engine.transcribe(str(dummy_wav))

        assert "--rpc" in captured_cmd
        rpc_idx = captured_cmd.index("--rpc")
        assert captured_cmd[rpc_idx + 1] == "192.168.0.220:50052"

        assert "--tensor-split" in captured_cmd
        ts_idx = captured_cmd.index("--tensor-split")
        assert captured_cmd[ts_idx + 1] == "60,40"
