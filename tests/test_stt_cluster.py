# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
AMEVA Unified Distributed RPC Cluster Orchestration Cold Tests for termux-stt.
Strict Protocol: Zero-Silent-Fallback & Fail-Fast Verification.
Component: [STT-CLUSTER]
"""

import socket
import pytest
from unittest.mock import patch, MagicMock

import termux_stt as stt
from termux_stt.exceptions import (
    ClusterConnectionError,
    ClusterConfigurationError,
)
from termux_stt.cluster import (
    parse_cluster_rpc_spec,
    verify_rpc_cluster_nodes,
    verify_rpc_cluster_health,
)
from termux_stt.engine.base import EngineConfig
from termux_stt.engine.whisper_engine import WhisperEngine
from termux_stt.cli.main import _run_cli


def test_parse_cluster_rpc_spec_valid():
    """Verify parsing and normalization of valid RPC specs."""
    servers_str = "192.0.2.11:50052, 192.0.2.12:50052"
    parsed = parse_cluster_rpc_spec(servers_str)
    assert parsed == ["192.0.2.11:50052", "192.0.2.12:50052"]

    servers_list = ["192.0.2.11:50052", "192.0.2.12:50052"]
    parsed2 = parse_cluster_rpc_spec(servers_list)
    assert parsed2 == ["192.0.2.11:50052", "192.0.2.12:50052"]

    assert parse_cluster_rpc_spec(None) == []
    assert parse_cluster_rpc_spec("") == []


def test_parse_cluster_rpc_spec_invalid():
    """Verify invalid RPC formats strictly raise ClusterConfigurationError."""
    with pytest.raises(ClusterConfigurationError):
        parse_cluster_rpc_spec("invalid_host_no_port")

    with pytest.raises(ClusterConfigurationError):
        parse_cluster_rpc_spec("host:not_a_number")

    with pytest.raises(ClusterConfigurationError):
        parse_cluster_rpc_spec("host:999999")  # Port out of range

    with pytest.raises(ClusterConfigurationError):
        parse_cluster_rpc_spec(12345)  # Invalid type


def test_verify_rpc_cluster_nodes_success():
    """Verify pre-flight check succeeds when all RPC nodes accept TCP connection."""
    servers = ["192.0.2.11:50052", "192.0.2.12:50052"]
    with patch("socket.create_connection") as mock_conn:
        mock_conn.return_value.__enter__.return_value = MagicMock()
        verify_rpc_cluster_nodes(servers, timeout=1.0)
        assert mock_conn.call_count == 2


def test_verify_rpc_cluster_nodes_fail_fast():
    """Verify Zero-Silent-Fallback: Unreachable node raises ClusterConnectionError immediately."""
    servers = ["192.0.2.11:50052", "192.0.2.12:50052"]

    def fake_connect(addr, timeout=None):
        host, port = addr
        if host == "192.0.2.12":
            raise ConnectionRefusedError("Connection refused by test worker")
        return MagicMock()

    with patch("socket.create_connection", side_effect=fake_connect):
        with pytest.raises(ClusterConnectionError) as exc_info:
            verify_rpc_cluster_nodes(servers, timeout=1.0)
        assert "Zero-Silent-Fallback Violation Prevented" in str(exc_info.value)
        assert "192.0.2.12:50052" in str(exc_info.value)


def test_verify_rpc_cluster_health_reporting():
    """Verify granular diagnostics from verify_rpc_cluster_health."""
    servers = ["192.0.2.11:50052", "192.0.2.12:50052"]

    def fake_connect(addr, timeout=None):
        host, port = addr
        if host == "192.0.2.12":
            raise socket.timeout("Timed out")
        return MagicMock()

    with patch("socket.create_connection", side_effect=fake_connect):
        health = verify_rpc_cluster_health(servers, timeout=1.0)
        assert health["all_healthy"] is False
        assert health["nodes"]["192.0.2.11:50052"]["reachable"] is True
        assert health["nodes"]["192.0.2.12:50052"]["reachable"] is False


def test_whisper_engine_cluster_args(tmp_path):
    """Verify WhisperEngine.transcribe injects cluster args and runs preflight verification."""
    dummy_wav = tmp_path / "speech.wav"
    dummy_wav.write_bytes(b"RIFF" + b"\x00" * 36 + b"data" + b"\x00" * 16)
    dummy_model = tmp_path / "model.bin"
    dummy_model.write_bytes(b"GGML" + b"\x00" * 32)

    config = EngineConfig(
        model_name=str(dummy_model),
        language="ko",
        device="cpu",
        threads=4,
        cluster_rpc_servers="192.0.2.11:50052, 192.0.2.12:50052",
        cluster_tensor_split="40,60",
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
         patch("termux_stt.engine.whisper_engine.verify_rpc_cluster_nodes") as mock_verify, \
         patch("termux_stt.audio.preprocessor.ensure_wav_format", return_value=str(dummy_wav)), \
         patch("termux_stt.platform.process_pool.run_isolated", side_effect=fake_run_isolated):

        res = engine.transcribe(str(dummy_wav))

        assert mock_verify.called
        assert "--rpc" in captured_cmd
        rpc_idx = captured_cmd.index("--rpc")
        assert captured_cmd[rpc_idx + 1] == "192.0.2.11:50052,192.0.2.12:50052"
        assert "--tensor-split" in captured_cmd
        ts_idx = captured_cmd.index("--tensor-split")
        assert captured_cmd[ts_idx + 1] == "40,60"


def test_cli_stt_cluster_rpc_servers_arg(tmp_path):
    """Verify CLI parses --cluster-rpc-servers and --cluster-tensor-split flags."""
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
            "--cluster-rpc-servers", "192.0.2.11:50052,192.0.2.12:50052",
            "--cluster-tensor-split", "50,50",
            "--engine", "whisper",
            "--device", "cpu",
        ]):
            _run_cli()

        assert mock_create.called
        kwargs = mock_create.call_args[1]
        assert kwargs["cluster_rpc_servers"] == "192.0.2.11:50052,192.0.2.12:50052"
        assert kwargs["cluster_tensor_split"] == "50,50"
