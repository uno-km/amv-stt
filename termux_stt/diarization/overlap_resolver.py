# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Multi-Label Target-Speaker VAD (TS-VAD) & Overlapped Speech Resolver.

Solves the classic cross-talk / interjection suppression problem in
single-stream diarization by dynamically profiling speaker voiceprints (CAM++)
and scanning long turns with a sliding window to detect concurrent / backchannel speech.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

__all__ = ["OverlapResolver"]


class OverlapResolver:
    """Detects and decouples overlapped speech & short interjections via TS-VAD.

    Architecture Inspired by:
      - Microsoft TS-VAD (Medennikov et al., Interspeech 2020)
      - Naver ClovaNote Multi-label Frame Classification (NEST)
      - PyAnnote Overlapped Speech Detection (Bredin et al., 2023)
    """

    def __init__(
        self,
        window_sec: float = 0.7,
        hop_sec: float = 0.15,
        interjection_threshold: float = 0.35,
        min_scan_duration: float = 2.5,
    ) -> None:
        self.window_sec = window_sec
        self.hop_sec = hop_sec
        self.interjection_threshold = interjection_threshold
        self.min_scan_duration = min_scan_duration

    @staticmethod
    def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculate cosine similarity between two 1D embedding vectors."""
        n1 = np.linalg.norm(v1)
        n2 = np.linalg.norm(v2)
        if n1 < 1e-9 or n2 < 1e-9:
            return 0.0
        return float(np.dot(v1, v2) / (n1 * n2))

    def extract_embedding(
        self, samples: np.ndarray, sr: int, start_sec: float, end_sec: float, extractor: Any
    ) -> Optional[np.ndarray]:
        """Extract a single L2-normalized embedding vector for an audio slice."""
        idx_s = max(0, int(start_sec * sr))
        idx_e = min(len(samples), int(end_sec * sr))
        if idx_e - idx_s < int(0.2 * sr):
            return None

        sub = samples[idx_s:idx_e]
        try:
            stream = extractor.create_stream()
            stream.accept_waveform(sr, sub)
            stream.input_finished()
            emb = np.array(extractor.compute(stream), dtype=np.float32)
            norm = np.linalg.norm(emb)
            if norm > 1e-9:
                emb = emb / norm
            return emb
        except Exception as exc:
            logger.debug("Failed to extract embedding [%.2f, %.2f]: %s", start_sec, end_sec, exc)
            return None

    def build_voiceprint_profiles(
        self,
        samples: np.ndarray,
        sr: int,
        intervals: List[Tuple[float, float, int]],
        extractor: Any,
    ) -> Dict[int, np.ndarray]:
        """Compute reference voiceprint centroid per speaker from non-overlapping segments."""
        speaker_vectors: Dict[int, List[np.ndarray]] = {}

        for start, end, spk in intervals:
            dur = end - start
            if dur < 0.5:
                continue
            # Sample up to 3 chunks per interval for robust centroid
            step = min(dur, 2.0)
            for t in np.arange(start, end, step):
                t_end = min(end, t + step)
                if t_end - t >= 0.4:
                    vec = self.extract_embedding(samples, sr, t, t_end, extractor)
                    if vec is not None:
                        speaker_vectors.setdefault(spk, []).append(vec)

        profiles: Dict[int, np.ndarray] = {}
        for spk, vecs in speaker_vectors.items():
            if vecs:
                centroid = np.mean(vecs, axis=0)
                norm = np.linalg.norm(centroid)
                profiles[spk] = centroid / norm if norm > 1e-9 else centroid

        return profiles

    def scan_multi_label_trajectory(
        self,
        samples: np.ndarray,
        sr: int,
        start_sec: float,
        end_sec: float,
        profiles: Dict[int, np.ndarray],
        extractor: Any,
    ) -> List[Tuple[float, float, Dict[int, float]]]:
        """Scan a time interval with sliding window and evaluate TS-VAD activation per speaker."""
        trajectory: List[Tuple[float, float, Dict[int, float]]] = []
        if len(profiles) < 2:
            return trajectory

        for t in np.arange(start_sec, end_sec - self.window_sec + 1e-5, self.hop_sec):
            t_end = min(end_sec, t + self.window_sec)
            vec = self.extract_embedding(samples, sr, t, t_end, extractor)
            if vec is None:
                continue

            scores: Dict[int, float] = {}
            for spk, ref in profiles.items():
                scores[spk] = self.cosine_similarity(vec, ref)

            trajectory.append((t, t_end, scores))

        return trajectory

    def resolve_overlaps(
        self,
        intervals: List[Tuple[float, float, int]],
        samples: np.ndarray,
        sr: int,
        extractor: Any,
    ) -> List[Tuple[float, float, int]]:
        """Refine and decouple speaker intervals by detecting micro-overlaps and interjections.

        Parameters
        ----------
        intervals : List[Tuple[float, float, int]]
            Raw diarization intervals (start, end, speaker_id).
        samples : np.ndarray
            Mono float32 audio waveform.
        sr : int
            Audio sample rate (e.g. 16000).
        extractor : Any
            Sherpa-ONNX SpeakerEmbeddingExtractor instance.

        Returns
        -------
        List[Tuple[float, float, int]]
            Refined intervals with detected interjection / overlap sub-segments decoupled.
        """
        if not intervals or extractor is None:
            return intervals

        # 1. Build Reference Voiceprints
        profiles = self.build_voiceprint_profiles(samples, sr, intervals, extractor)
        if len(profiles) < 2:
            return intervals

        resolved: List[Tuple[float, float, int]] = []

        for start, end, dominant_spk in intervals:
            dur = end - start
            if dur < self.min_scan_duration:
                resolved.append((start, end, dominant_spk))
                continue

            # 2. Multi-label scan along the long interval
            trajectory = self.scan_multi_label_trajectory(
                samples, sr, start, end, profiles, extractor
            )
            if not trajectory:
                resolved.append((start, end, dominant_spk))
                continue

            # 3. Search for secondary speaker peaks (interjection / cross-talk)
            other_speakers = [s for s in profiles if s != dominant_spk]
            detected_splits: List[Tuple[float, float, int]] = []

            for other_spk in other_speakers:
                # Find frames where other speaker activity rises above threshold
                peaks = [
                    (t_s, t_e, sc[other_spk])
                    for t_s, t_e, sc in trajectory
                    if sc.get(other_spk, 0.0) >= self.interjection_threshold
                    and sc.get(other_spk, 0.0) >= sc.get(dominant_spk, 0.0) * 0.75
                ]

                if peaks:
                    # Group consecutive peaks into an interjection segment
                    p_start = min(p[0] for p in peaks)
                    p_end = max(p[1] for p in peaks)
                    # Constraint check: must be at least 0.3s and strictly within bounds
                    if (p_end - p_start) >= 0.3 and (p_start > start + 0.3) and (p_end < end - 0.3):
                        detected_splits.append((p_start, p_end, other_spk))

            if not detected_splits:
                resolved.append((start, end, dominant_spk))
                continue

            # 4. Splice the interval around the detected interjection
            detected_splits.sort(key=lambda x: x[0])
            curr_pos = start
            for s_start, s_end, interj_spk in detected_splits:
                if s_start > curr_pos + 0.2:
                    resolved.append((curr_pos, s_start, dominant_spk))
                resolved.append((s_start, s_end, interj_spk))
                curr_pos = s_end

            if curr_pos < end - 0.2:
                resolved.append((curr_pos, end, dominant_spk))

        resolved.sort(key=lambda x: x[0])
        return resolved
