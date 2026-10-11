# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""Online (streaming) neural speaker diarization for Termux.

Performs real-time frame-by-frame or chunk-by-chunk speaker diarization
using lightweight VAD, on-device speaker embedding (CAM++ / 3D-Speaker),
and online centroid-based incremental clustering.
"""

import logging
import math
import os
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

__all__ = ["OnlineSpeakerDiarizer", "OnlineSpeakerSegment"]


@dataclass
class OnlineSpeakerSegment:
    """Represents a speaker segment identified in online streaming."""
    speaker: str
    start: float
    end: float
    confidence: float
    is_speech: bool = True


class OnlineSpeakerDiarizer:
    """Real-time online speaker diarizer with incremental centroid tracking."""

    def __init__(
        self,
        num_speakers: Optional[int] = None,
        threshold: float = 0.65,
        energy_threshold: float = 0.008,
        sample_rate: int = 16000,
        alpha: float = 0.85,
        threads: int = 4,
        device: str = "cpu",
    ) -> None:
        """Initialize the online diarizer.

        Parameters
        ----------
        num_speakers : Optional[int]
            Constrain maximum allowed distinct speakers (None for dynamic growth).
        threshold : float
            Cosine similarity threshold to join an existing speaker cluster.
        energy_threshold : float
            RMS energy threshold below which audio chunk is marked as silence.
        sample_rate : int
            Audio sample rate (defaults to 16000 Hz).
        alpha : float
            Moving average weight for centroid updates (0 < alpha < 1).
        threads : int
            Thread count for inference.
        device : str
            Execution target ('cpu' or 'gpu').
        """
        self.num_speakers = num_speakers
        self.threshold = threshold
        self.energy_threshold = energy_threshold
        self.sample_rate = sample_rate
        self.alpha = alpha
        self.threads = threads
        self.device = device

        # Speaker ID -> Centroid vector (normalized)
        self._centroids: Dict[str, List[float]] = {}
        # Speaker ID -> Number of assigned chunks
        self._counts: Dict[str, int] = {}
        # Enrolled ground-truth speakers (cannot be evicted)
        self._enrolled: set = set()

        self._speaker_index = 1
        self._extractor: Optional[Any] = None
        self._init_extractor()

    def _init_extractor(self) -> None:
        """Lazily initialize sherpa-onnx embedding extractor if available."""
        try:
            import sherpa_onnx
            from termux_stt.models.hub import ModelHub

            emb_path = ModelHub.ensure_model("sherpa", "3dspeaker-campplus")
            if os.path.exists(emb_path):
                config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                    model=emb_path,
                    num_threads=self.threads,
                    provider="cpu" if self.device == "cpu" else "vulkan",
                )
                self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
                logger.info("OnlineSpeakerDiarizer: initialized native 3D-Speaker CAM++ extractor")
        except Exception as exc:
            logger.debug("OnlineSpeakerDiarizer: native extractor unavailable (%s), using native acoustic signature fallback", exc)
            self._extractor = None

    def reset(self) -> None:
        """Reset internal clusters while preserving enrolled speaker voiceprints."""
        preserved = {k: v for k, v in self._centroids.items() if k in self._enrolled}
        self._centroids = preserved
        self._counts = {k: 1 for k in self._enrolled}
        self._speaker_index = len(self._enrolled) + 1

    def enroll_speaker(self, speaker_name: str, pcm_bytes: bytes) -> None:
        """Enroll a known speaker voiceprint before real-time streaming."""
        vec = self._compute_embedding(pcm_bytes)
        if vec:
            self._centroids[speaker_name] = vec
            self._counts[speaker_name] = 1
            self._enrolled.add(speaker_name)
            logger.info("Enrolled speaker '%s' with voiceprint signature (dim=%d)", speaker_name, len(vec))

    def process_chunk(
        self,
        pcm_bytes: bytes,
        start_sec: float,
        end_sec: float,
    ) -> OnlineSpeakerSegment:
        """Process a streaming audio chunk and return speaker classification."""
        # 1. Voice Activity Detection (RMS energy gate)
        energy = self._compute_rms(pcm_bytes)
        if energy < self.energy_threshold:
            return OnlineSpeakerSegment(
                speaker="Silence",
                start=start_sec,
                end=end_sec,
                confidence=1.0,
                is_speech=False,
            )

        # 2. Extract normalized embedding vector
        vec = self._compute_embedding(pcm_bytes)
        if not vec:
            return OnlineSpeakerSegment(
                speaker="Speaker_Unknown",
                start=start_sec,
                end=end_sec,
                confidence=0.0,
                is_speech=True,
            )

        # 3. Match against existing centroids
        best_speaker, best_similarity = self._match_centroid(vec)

        # Decision logic:
        # Case A: Cluster list is empty
        if not self._centroids:
            assigned = f"Speaker_{self._speaker_index}"
            self._speaker_index += 1
            self._centroids[assigned] = vec
            self._counts[assigned] = 1
            return OnlineSpeakerSegment(speaker=assigned, start=start_sec, end=end_sec, confidence=1.0)

        # Case B: Exceeds threshold -> match confirmed
        if best_similarity >= self.threshold:
            self._update_centroid(best_speaker, vec)
            return OnlineSpeakerSegment(
                speaker=best_speaker,
                start=start_sec,
                end=end_sec,
                confidence=best_similarity,
            )

        # Case C: Below threshold, but max speaker count constraint reached
        if self.num_speakers is not None and len(self._centroids) >= self.num_speakers:
            # Force assignment to closest centroid to avoid unbounded cluster drift
            self._update_centroid(best_speaker, vec)
            return OnlineSpeakerSegment(
                speaker=best_speaker,
                start=start_sec,
                end=end_sec,
                confidence=best_similarity,
            )

        # Case D: Below threshold and cluster space available -> spawn new speaker
        new_spk = f"Speaker_{self._speaker_index}"
        self._speaker_index += 1
        self._centroids[new_spk] = vec
        self._counts[new_spk] = 1
        return OnlineSpeakerSegment(
            speaker=new_spk,
            start=start_sec,
            end=end_sec,
            confidence=1.0,
        )

    # ------------------------------------------------------------------
    # Math & Acoustic Helpers
    # ------------------------------------------------------------------

    def _compute_rms(self, pcm_bytes: bytes) -> float:
        """Compute normalized Root Mean Square energy from 16-bit PCM bytes."""
        count = len(pcm_bytes) // 2
        if count == 0:
            return 0.0
        shorts = struct.unpack(f"<{count}h", pcm_bytes[: count * 2])
        sum_sq = sum(s * s for s in shorts)
        rms = math.sqrt(sum_sq / count)
        return rms / 32768.0

    def _compute_embedding(self, pcm_bytes: bytes) -> Optional[List[float]]:
        """Extract high-dimensional L2-normalized embedding."""
        if len(pcm_bytes) < 320:  # < 10ms at 16kHz
            return None

        # 1. Native sherpa-onnx extractor if initialized
        if self._extractor is not None:
            try:
                import numpy as np
                count = len(pcm_bytes) // 2
                shorts = struct.unpack(f"<{count}h", pcm_bytes[: count * 2])
                floats = np.array(shorts, dtype=np.float32) / 32768.0
                stream = self._extractor.create_stream()
                stream.accept_waveform(sample_rate=self.sample_rate, waveform=floats)
                if self._extractor.is_ready(stream):
                    embedding = self._extractor.compute(stream)
                    vec = list(embedding)
                    return self._l2_normalize(vec)
            except Exception as exc:
                logger.debug("Sherpa extractor computation failed: %s, falling back to signature", exc)

        # 2. Pure Python / standard library frequency-energy acoustic signature
        # Generates a stable 64-dimensional spectral vector
        return self._compute_spectral_signature(pcm_bytes)

    def _compute_spectral_signature(self, pcm_bytes: bytes, num_bins: int = 64) -> List[float]:
        """Compute frequency-domain filterbank energy spectrum."""
        import numpy as np
        count = len(pcm_bytes) // 2
        if count < num_bins:
            return [0.0] * num_bins
        shorts = struct.unpack(f"<{count}h", pcm_bytes[: count * 2])
        floats = np.array(shorts, dtype=np.float32) / 32768.0

        # Real FFT to obtain frequency magnitude spectrum
        fft_vals = np.abs(np.fft.rfft(floats))
        fft_len = len(fft_vals)

        # Frequency bin grouping
        bin_size = max(1, fft_len // num_bins)
        bins: List[float] = []
        for i in range(num_bins):
            start_idx = i * bin_size
            end_idx = min(fft_len, (i + 1) * bin_size)
            if start_idx < end_idx:
                energy = float(np.mean(fft_vals[start_idx:end_idx]))
            else:
                energy = 0.0
            bins.append(energy)

        return self._l2_normalize(bins)

    def _match_centroid(self, vec: List[float]) -> Tuple[str, float]:
        """Find the existing speaker centroid with highest cosine similarity."""
        best_speaker = "Speaker_1"
        best_sim = -1.0
        for spk, centroid in self._centroids.items():
            sim = self._cosine_similarity(vec, centroid)
            if sim > best_sim:
                best_sim = sim
                best_speaker = spk
        return best_speaker, max(0.0, best_sim)

    def _update_centroid(self, speaker: str, new_vec: List[float]) -> None:
        """Update centroid with moving average and re-normalize."""
        cur = self._centroids[speaker]
        # Exponential moving average: cur * alpha + new_vec * (1 - alpha)
        updated = [
            cur[i] * self.alpha + new_vec[i] * (1.0 - self.alpha)
            for i in range(len(cur))
        ]
        self._centroids[speaker] = self._l2_normalize(updated)
        self._counts[speaker] = self._counts.get(speaker, 0) + 1

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two unit vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        return dot

    @staticmethod
    def _l2_normalize(vec: List[float]) -> List[float]:
        """L2-normalize a floating point vector."""
        norm = math.sqrt(sum(x * x for x in vec))
        if norm < 1e-12:
            return vec
        return [x / norm for x in vec]
