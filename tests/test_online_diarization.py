# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""Unit and integration tests for real-time online neural speaker diarization."""

import math
import struct
import unittest
from unittest.mock import MagicMock, patch

from termux_stt.diarization.online_diarizer import (
    OnlineSpeakerDiarizer,
    OnlineSpeakerSegment,
)
from termux_stt.export.result import Segment, TranscriptResult


def _generate_pcm_tone(freq_hz: float, duration_sec: float = 1.5, sample_rate: int = 16000, volume: float = 0.5) -> bytes:
    """Generate 16-bit mono PCM tone for deterministic acoustic signature testing."""
    num_samples = int(sample_rate * duration_sec)
    shorts = []
    for i in range(num_samples):
        val = int(volume * 32767.0 * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)))
        shorts.append(max(-32768, min(32767, val)))
    return struct.pack(f"<{num_samples}h", *shorts)


class TestOnlineSpeakerDiarizer(unittest.TestCase):
    """Test suite for OnlineSpeakerDiarizer."""

    def setUp(self):
        self.diarizer = OnlineSpeakerDiarizer(
            num_speakers=2,
            threshold=0.60,
            energy_threshold=0.005,
            sample_rate=16000,
        )

    def test_silence_detection(self):
        """Verify that pure silence is recognized as non-speech segment."""
        silence_pcm = b"\x00" * (16000 * 2)  # 1 sec of digital silence
        seg = self.diarizer.process_chunk(silence_pcm, start_sec=0.0, end_sec=1.0)
        self.assertFalse(seg.is_speech)
        self.assertEqual(seg.speaker, "Silence")

    def test_speaker_differentiation(self):
        """Verify that distinct acoustic frequencies generate distinct speaker clusters."""
        speaker_a_pcm = _generate_pcm_tone(freq_hz=300.0, duration_sec=1.5)
        speaker_b_pcm = _generate_pcm_tone(freq_hz=1800.0, duration_sec=1.5)

        seg1 = self.diarizer.process_chunk(speaker_a_pcm, start_sec=0.0, end_sec=1.5)
        self.assertTrue(seg1.is_speech)
        self.assertEqual(seg1.speaker, "Speaker_1")

        # Second chunk with different acoustic pattern should spawn Speaker_2
        seg2 = self.diarizer.process_chunk(speaker_b_pcm, start_sec=1.5, end_sec=3.0)
        self.assertTrue(seg2.is_speech)
        self.assertEqual(seg2.speaker, "Speaker_2")

        # Third chunk identical to Speaker A should match Speaker_1
        seg3 = self.diarizer.process_chunk(speaker_a_pcm, start_sec=3.0, end_sec=4.5)
        self.assertTrue(seg3.is_speech)
        self.assertEqual(seg3.speaker, "Speaker_1")

    def test_num_speakers_constraint(self):
        """Verify that num_speakers constraint prevents unbounded cluster growth."""
        spk_a = _generate_pcm_tone(freq_hz=300.0)
        spk_b = _generate_pcm_tone(freq_hz=900.0)
        spk_c = _generate_pcm_tone(freq_hz=2400.0)

        self.diarizer.process_chunk(spk_a, 0.0, 1.5)
        self.diarizer.process_chunk(spk_b, 1.5, 3.0)

        # Third distinct tone should be constrained to existing clusters
        seg_c = self.diarizer.process_chunk(spk_c, 3.0, 4.5)
        self.assertIn(seg_c.speaker, ["Speaker_1", "Speaker_2"])

    def test_speaker_enrollment(self):
        """Verify that prior enrolled voiceprint takes priority."""
        diarizer = OnlineSpeakerDiarizer(threshold=0.55)
        alice_pcm = _generate_pcm_tone(freq_hz=440.0)
        diarizer.enroll_speaker("Alice", alice_pcm)

        test_pcm = _generate_pcm_tone(freq_hz=440.0)
        seg = diarizer.process_chunk(test_pcm, 0.0, 1.5)
        self.assertEqual(seg.speaker, "Alice")
        self.assertGreater(seg.confidence, 0.55)


class TestHybridStreamMicDiarize(unittest.TestCase):
    """Test suite for HybridEngine stream_mic_diarize integration."""

    @patch("termux_stt.audio.mic.MicCapture.stream_continuous")
    def test_stream_mic_diarize_mock(self, mock_mic_stream):
        """Verify that stream_mic_diarize yields valid Segments with speaker labels."""
        from termux_stt import create_engine
        from termux_stt.engine.base import EngineConfig
        from termux_stt.engine.hybrid_engine import HybridEngine

        # Mock mic yielding 2 audio chunks
        chunk1 = _generate_pcm_tone(freq_hz=350.0, duration_sec=1.5)
        chunk2 = _generate_pcm_tone(freq_hz=1600.0, duration_sec=1.5)
        mock_mic_stream.return_value = iter([chunk1, chunk2])

        config = EngineConfig(engine="hybrid", model="tiny", lang="ko", threads=2, num_speakers=2)
        engine = HybridEngine(config)

        # Mock whisper transcription return
        engine._whisper.transcribe = MagicMock(side_effect=[
            TranscriptResult(text="안녕하세요 첫번째 발화입니다.", segments=[Segment(start=0.0, end=1.5, text="안녕하세요 첫번째 발화입니다.")]),
            TranscriptResult(text="반갑습니다 두번째 발화입니다.", segments=[Segment(start=0.0, end=1.5, text="반갑습니다 두번째 발화입니다.")]),
        ])

        segments = list(engine.stream_mic_diarize(chunk_sec=1.5, num_speakers=2))
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].speaker, "Speaker_1")
        self.assertIn("첫번째", segments[0].text)
        self.assertEqual(segments[1].speaker, "Speaker_2")
        self.assertIn("두번째", segments[1].text)


if __name__ == "__main__":
    unittest.main()
