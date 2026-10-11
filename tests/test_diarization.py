# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import pytest

from termux_stt.diarization.clustering import KMeans, cosine_similarity, euclidean_distance
from termux_stt.diarization.mapper import SpeakerMapper
from termux_stt.export.result import Segment


def test_distance_and_similarity():
    vec_a = [1.0, 0.0, 0.0]
    vec_b = [0.0, 1.0, 0.0]
    vec_c = [2.0, 0.0, 0.0]

    # Orthogonal
    assert abs(cosine_similarity(vec_a, vec_b) - 0.0) < 1e-6
    # Parallel
    assert abs(cosine_similarity(vec_a, vec_c) - 1.0) < 1e-6

    # Euclidean
    assert abs(euclidean_distance([0.0, 0.0], [3.0, 4.0]) - 5.0) < 1e-6

    # Dimension mismatch
    with pytest.raises(ValueError):
        euclidean_distance([1.0], [1.0, 2.0])


def test_kmeans_2clusters_separation():
    # Cluster A around (1, 1), Cluster B around (10, 10)
    data = [
        [0.9, 1.1], [1.0, 1.0], [1.2, 0.8],
        [9.9, 10.1], [10.0, 10.0], [10.2, 9.8]
    ]
    kmeans = KMeans(n_clusters=2, seed=42)
    kmeans.fit(data)

    labels = kmeans.labels_
    # First 3 should share one label, last 3 should share another
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] == labels[4] == labels[5]
    assert labels[0] != labels[3]


def test_kmeans_adaptive_sample_count():
    # Only 1 sample with 2 requested clusters -> must not crash, should adapt
    data = [[1.0, 2.0]]
    kmeans = KMeans(n_clusters=2, seed=42)
    kmeans.fit(data)
    assert len(kmeans.labels_) == 1
    assert kmeans.labels_[0] == 0


def test_speaker_mapper_overlap_alignment():
    segments = [
        Segment(start=0.0, end=2.0, text="Hello"),
        Segment(start=2.5, end=4.5, text="World"),
    ]
    # Speaker 0 active [0.0 - 2.2], Speaker 1 active [2.2 - 5.0]
    speaker_labels = [
        (0.0, 2.2, 0),
        (2.2, 5.0, 1),
    ]

    mapper = SpeakerMapper()
    aligned = mapper.align(segments, speaker_labels)

    assert len(aligned) == 2
    assert aligned[0].speaker == "Speaker_0"
    assert aligned[0].text == "Hello"
    assert aligned[1].speaker == "Speaker_1"
    assert aligned[1].text == "World"


def test_speaker_mapper_empty_labels_fallback_unknown():
    # No speaker_labels provided -> all segments honestly marked as Speaker_Unknown
    segments = [
        Segment(start=0.0, end=1.0, text="Speaker one speaking"),
        Segment(start=1.2, end=2.0, text="Still speaker one"),
        Segment(start=3.5, end=4.5, text="Speaker two speaking after long pause"),
    ]
    mapper = SpeakerMapper()
    aligned = mapper.align(segments, [], num_speakers=2)

    assert aligned[0].speaker == "Speaker_Unknown"
    assert aligned[1].speaker == "Speaker_Unknown"
    assert aligned[2].speaker == "Speaker_Unknown"


def test_sherpa_diarizer_strict_opencl_protocol():
    from termux_stt.diarization.sherpa_diarizer import SherpaDiarizer

    # 1. Explicit opencl -> opencl provider allowed
    d_opencl = SherpaDiarizer(device="opencl")
    assert d_opencl._determine_provider() == "opencl"

    # 2. vulkan / gpu -> vulkan provider (never silently opencl)
    from unittest.mock import patch

    with patch("ameva_device.runtime_guard.installed_runtime_version", return_value="2.8.1"):
        d_vulkan = SherpaDiarizer(device="vulkan")
        assert d_vulkan._determine_provider() == "vulkan"
        assert d_vulkan._determine_provider() != "opencl"

        d_gpu = SherpaDiarizer(device="gpu")
        assert d_gpu._determine_provider() == "vulkan"
        assert d_gpu._determine_provider() != "opencl"

    # 3. auto / cpu -> cpu provider (never opencl)
    d_auto = SherpaDiarizer(device="auto")
    assert d_auto._determine_provider() == "cpu"
    assert d_auto._determine_provider() != "opencl"

    d_cpu = SherpaDiarizer(device="cpu")
    assert d_cpu._determine_provider() == "cpu"
    assert d_cpu._determine_provider() != "opencl"


def test_sherpa_diarizer_audio_sample_loader(tmp_path):
    import array
    import wave
    from termux_stt.diarization.sherpa_diarizer import SherpaDiarizer

    wav_file = str(tmp_path / "test_16k_mono.wav")
    sr = 16000
    # Create 100 samples: half 0, half max int16 (32767)
    raw_data = array.array("h", [0] * 50 + [32767] * 50).tobytes()

    with wave.open(wav_file, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw_data)

    samples = SherpaDiarizer._load_audio_samples(wav_file)
    assert len(samples) == 100
    assert abs(samples[0] - 0.0) < 1e-5
    assert abs(samples[75] - (32767 / 32768.0)) < 1e-4


def test_sherpa_diarizer_2tier_dispatch(monkeypatch):
    from termux_stt.diarization.sherpa_diarizer import SherpaDiarizer

    diarizer = SherpaDiarizer()
    monkeypatch.setattr("termux_stt.diarization.sherpa_diarizer.preprocess", lambda p, **kw: p)
    monkeypatch.setattr(diarizer, "_resolve_models", lambda: ("/mock/seg.onnx", "/mock/emb.onnx"))

    # Test 1: Tier 1 success
    called_tier1 = []
    called_tier2 = []

    def mock_tier1(wav, num_spk, seg, emb):
        called_tier1.append(True)
        return [(0.0, 1.5, 0), (1.5, 3.0, 1)]

    def mock_tier2(wav, num_spk, seg, emb):
        called_tier2.append(True)
        return [(0.0, 1.5, 0), (1.5, 3.0, 1)]

    monkeypatch.setattr(diarizer, "_diarize_in_process", mock_tier1)
    monkeypatch.setattr(diarizer, "_diarize_subprocess", mock_tier2)

    res = diarizer.diarize_audio("/mock/test.wav", num_speakers=2)
    assert len(res) == 2
    assert len(called_tier1) == 1
    assert len(called_tier2) == 0

    # Test 2: Tier 1 fails (ImportError) -> falls back to Tier 2
    called_tier1.clear()
    called_tier2.clear()

    def mock_tier1_fail(wav, num_spk, seg, emb):
        called_tier1.append(True)
        raise ImportError("No sherpa_onnx")

    monkeypatch.setattr(diarizer, "_diarize_in_process", mock_tier1_fail)
    res2 = diarizer.diarize_audio("/mock/test.wav", num_speakers=2)
    assert len(res2) == 2
    assert len(called_tier1) == 1
    assert len(called_tier2) == 1


def test_sherpa_diarizer_speed_modes():
    from termux_stt.diarization.sherpa_diarizer import SherpaDiarizer

    # 1. balanced default -> 0.25
    d_balanced = SherpaDiarizer(speed_mode="balanced")
    assert abs(d_balanced.window_shift_ratio - 0.25) < 1e-4

    # 2. fast -> 0.50
    d_fast = SherpaDiarizer(speed_mode="fast")
    assert abs(d_fast.window_shift_ratio - 0.50) < 1e-4

    # 3. accurate -> 0.10
    d_acc = SherpaDiarizer(speed_mode="accurate")
    assert abs(d_acc.window_shift_ratio - 0.10) < 1e-4

    # 4. explicit custom window_shift_ratio overrides speed_mode
    d_custom = SherpaDiarizer(speed_mode="fast", window_shift_ratio=0.18)
    assert abs(d_custom.window_shift_ratio - 0.18) < 1e-4


