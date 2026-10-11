# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""Unit tests for OverlapResolver (TS-VAD and micro-segmentation)."""

import numpy as np
import pytest
from termux_stt.diarization.overlap_resolver import OverlapResolver


class DummyStream:
    def __init__(self, sample_rate, waveform):
        self.sr = sample_rate
        self.waveform = waveform

    def accept_waveform(self, sr, wf):
        pass

    def input_finished(self):
        pass


class DummyExtractor:
    """Mock extractor that outputs distinct embeddings based on time window."""

    def __init__(self):
        # Two distinct 192-dim orthogonal basis vectors
        self.spk0_vec = np.zeros(192, dtype=np.float32)
        self.spk0_vec[0] = 1.0

        self.spk1_vec = np.zeros(192, dtype=np.float32)
        self.spk1_vec[1] = 1.0

        self.last_waveform = None

    def create_stream(self):
        return DummyStream(16000, None)

    def compute(self, stream):
        # We simulate that around 3.2s ~ 4.0s in 16kHz audio, spk1 is speaking
        # (Assuming 16000 sr, indices 51200 ~ 64000)
        wf = self.last_waveform
        if wf is not None and len(wf) > 0:
            mean_val = np.mean(wf)
            if mean_val > 0.5:
                return self.spk1_vec
        return self.spk0_vec


def test_cosine_similarity():
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([1.0, 0.0, 0.0])
    v3 = np.array([0.0, 1.0, 0.0])

    assert pytest.approx(OverlapResolver.cosine_similarity(v1, v2)) == 1.0
    assert pytest.approx(OverlapResolver.cosine_similarity(v1, v3)) == 0.0


def test_build_voiceprint_profiles():
    resolver = OverlapResolver()
    extractor = DummyExtractor()
    sr = 16000
    samples = np.zeros(sr * 10, dtype=np.float32)

    intervals = [(0.0, 2.0, 0), (2.5, 4.5, 1)]
    profiles = resolver.build_voiceprint_profiles(samples, sr, intervals, extractor)

    assert 0 in profiles
    assert 1 in profiles
    assert len(profiles[0]) == 192


def test_resolve_overlaps_no_split_short_intervals():
    resolver = OverlapResolver(min_scan_duration=3.0)
    extractor = DummyExtractor()
    sr = 16000
    samples = np.zeros(sr * 5, dtype=np.float32)

    # All intervals shorter than 3.0s -> no splits
    intervals = [(0.0, 1.5, 0), (1.5, 2.5, 1)]
    resolved = resolver.resolve_overlaps(intervals, samples, sr, extractor)

    assert len(resolved) == 2
    assert resolved == intervals
