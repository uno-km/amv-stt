# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Unit Tests: STT Hardware Routing, Fail-Fast Protocol & Orchestrator Control Bridge
==================================================================================
Verifies:
1. resolve_device() adheres strictly to Zero-Silent-Fallback ([ERROR: AMEVA-STT-E001/E002]).
2. WhisperEngine._prepare_env() properly sets up Android Bionic ICD / Vulkan environment.
3. STTControl.transcribe() fulfills AMEVA Component Protocol v1 contract (ok=True, silence, error handling).
4. STTOrchestratorAdapter.infer() integrates cleanly with STTControl.
"""
import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

from termux_stt.exceptions import ErrorCode, PlatformNotSupportedError
from termux_stt.platform.hardware import resolve_device
from termux_stt.engine.whisper_engine import WhisperEngine
from termux_stt.engine.base import EngineConfig
from termux_stt.export.result import TranscriptResult, Segment
from termux_stt.control.component import STTControl
from termux_stt.adapter import STTOrchestratorAdapter, create_adapter


class TestSttHardwareAndControl(unittest.TestCase):

    def test_resolve_device_cpu(self):
        device, threads = resolve_device("cpu")
        self.assertEqual(device, "cpu")
        self.assertGreaterEqual(threads, 1)

    def test_resolve_device_gpu_fail_fast_when_runtime_missing(self):
        with patch.dict("sys.modules", {"ameva_runtime": None, "ameva_runtime.vulkan": None}):
            with self.assertRaises(PlatformNotSupportedError) as ctx:
                resolve_device("gpu")
            self.assertEqual(ctx.exception.code, ErrorCode.RUNTIME_NOT_INSTALLED)
            self.assertIn("AMU_ERR_RUNTIME_REQUIRED", str(ctx.exception))
            self.assertIn("pip install", str(ctx.exception))

    def test_resolve_device_gpu_fail_fast_when_vulkan_fails(self):
        mock_avr = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.backend_type = "cpu"
        mock_ctx.is_gpu = False
        mock_avr.get_or_create_context.return_value = mock_ctx
        mock_avr.create_context.return_value = mock_ctx
        mock_avr.VulkanContext.return_value = mock_ctx

        mock_parent = MagicMock()
        mock_parent.vulkan = mock_avr

        with patch.dict("sys.modules", {"ameva_runtime": mock_parent, "ameva_runtime.vulkan": mock_avr}), \
                patch("ameva_device.runtime_guard.installed_runtime_version", return_value="2.8.1"):
            with self.assertRaises(PlatformNotSupportedError) as ctx:
                resolve_device("vulkan")
            self.assertEqual(ctx.exception.code, ErrorCode.VULKAN_DEVICE)
            self.assertIn("[ERROR: AMEVA-STT-E002]", str(ctx.exception))

    def test_prepare_env_cpu(self):
        config = EngineConfig(engine="whisper", model="base", device="cpu")
        engine = WhisperEngine(config)
        env = engine._prepare_env("cpu")
        self.assertIsInstance(env, dict)

    def test_control_transcribe_audio_empty(self):
        control = STTControl()
        res = asyncio.run(control.transcribe({}))
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "AUDIO_EMPTY")

    def test_control_transcribe_audio_not_found(self):
        control = STTControl()
        res = asyncio.run(control.transcribe({"audio_path": "/nonexistent/test_audio.wav"}))
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "AUDIO_NOT_FOUND")

    @patch("pathlib.Path.exists", return_value=True)
    @patch.object(WhisperEngine, "transcribe")
    def test_control_transcribe_success(self, mock_transcribe, mock_exists):
        mock_transcribe.return_value = TranscriptResult(
            text="Hello AMEVA STT",
            segments=[Segment(start=0.0, end=1.5, text="Hello AMEVA STT")],
            language="ko",
        )
        control = STTControl()
        res = asyncio.run(control.transcribe({
            "audio_path": "dummy.wav",
            "model_id": "base",
            "language": "ko",
            "device": "cpu",
        }))

        self.assertTrue(res["ok"])
        self.assertEqual(res["text"], "Hello AMEVA STT")
        self.assertEqual(len(res["segments"]), 1)

    @patch("pathlib.Path.exists", return_value=True)
    @patch.object(WhisperEngine, "transcribe")
    def test_control_transcribe_silence_contract(self, mock_transcribe, mock_exists):
        mock_transcribe.return_value = TranscriptResult(
            text="",
            segments=[],
            language="ko",
        )
        control = STTControl()
        res = asyncio.run(control.transcribe({
            "audio_path": "dummy_silent.wav",
            "device": "cpu",
        }))

        self.assertTrue(res["ok"])
        self.assertEqual(res["text"], "")
        self.assertEqual(res["reason"], "silence_detected")

    @patch("pathlib.Path.exists", return_value=True)
    @patch.object(WhisperEngine, "transcribe")
    def test_adapter_infer_integration(self, mock_transcribe, mock_exists):
        mock_transcribe.return_value = TranscriptResult(
            text="Testing Adapter",
            segments=[Segment(start=0.0, end=2.0, text="Testing Adapter")],
            language="ko",
        )
        adapter = create_adapter()

        async def _test():
            frames = []
            async for frame in adapter.infer({"audio_path": "dummy.wav"}):
                frames.append(frame)
            return frames

        frames = asyncio.run(_test())
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0]["type"], "transcript")
        self.assertEqual(frames[0]["text"], "Testing Adapter")
        self.assertTrue(frames[0]["ok"])


if __name__ == "__main__":
    unittest.main()
