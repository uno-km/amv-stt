# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Sherpa-ONNX Native Speaker Diarization Engine.

Leverages PyAnnote Segmentation 3.0 and 3D-Speaker CAM++ embedding models
via sherpa-onnx-offline-speaker-diarization C++ NDK binary.
"""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from termux_stt.audio.preprocessor import preprocess
from termux_stt.export.result import DiarizedResult, Segment
from termux_stt.models.hub import ModelHub
from termux_stt.platform.process_pool import run_isolated

logger = logging.getLogger(__name__)

__all__ = ["SherpaDiarizer"]


class SherpaDiarizer:
    """High-accuracy on-device neural speaker diarization via Sherpa-ONNX.

    Uses:
      - PyAnnote 3.0 ONNX model for overlap-aware speech segmentation
      - 3D-Speaker CAM++ ONNX model for 192-dim speaker embeddings
      - Fast spectral/agglomerative clustering on-device
    """

    def __init__(
        self,
        segmentation_model: str = "pyannote-segmentation-3-0",
        embedding_model: str = "3dspeaker-campplus",
        num_speakers: Optional[int] = None,
        threshold: float = 0.65,
        threads: Optional[int] = None,
        device: str = "auto",
        provider: str = "cpu",
        speed_mode: str = "balanced",
        window_shift_ratio: Optional[float] = None,
    ) -> None:
        self.segmentation_model_name = segmentation_model
        self.embedding_model_name = embedding_model
        self.num_speakers = num_speakers
        self.threshold = threshold
        self.threads = threads or min(os.cpu_count() or 4, 4)
        self.device = str(device or "auto").strip().lower()
        self.provider = provider

        # Speed mode resolution for PyAnnote sliding window
        # balanced (0.25): 2.5x speedup with high accuracy
        # fast (0.50): 4x speedup for low latency
        # accurate (0.10): dense overlapping segmentation
        self.speed_mode = str(speed_mode or "balanced").strip().lower()
        if window_shift_ratio is not None:
            self.window_shift_ratio = float(window_shift_ratio)
        elif self.speed_mode in ("fast", "turbo"):
            self.window_shift_ratio = 0.50
        elif self.speed_mode in ("accurate", "high"):
            self.window_shift_ratio = 0.10
        else:
            self.window_shift_ratio = 0.25

    @staticmethod
    def _find_binary(name: str = "sherpa-onnx-offline-speaker-diarization") -> str:
        """Locate sherpa-onnx-offline-speaker-diarization executable."""
        found = shutil.which(name)
        if found:
            return found
        candidates = [
            Path.home() / ".local" / "bin" / name,
            Path(f"/data/data/com.termux/files/home/.local/bin/{name}"),
            Path(f"/data/data/com.termux/files/usr/bin/{name}"),
            Path(f"/data/data/com.termux/files/usr/local/bin/{name}"),
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        raise FileNotFoundError(
            f"Cannot locate '{name}' executable.\n"
            f"Please run 'termux-stt install --engine diarization' or in Python:\n"
            f"  from termux_stt.platform.installer import EngineInstaller\n"
            f"  EngineInstaller.install_diarization()"
        )

    def _resolve_models(self) -> Tuple[str, str]:
        """Locate PyAnnote segmentation and CAM++ embedding ONNX models via ModelHub."""
        seg_dir = ModelHub.ensure_model("sherpa", self.segmentation_model_name)
        emb_path = ModelHub.ensure_model("sherpa", self.embedding_model_name)

        # Robust segmentation ONNX search
        seg_model = None
        search_dirs = [seg_dir]
        if os.path.isfile(seg_dir):
            parent = os.path.dirname(seg_dir)
            search_dirs.extend([
                parent,
                os.path.join(parent, "sherpa-onnx-pyannote-segmentation-3-0"),
                os.path.join(parent, "pyannote-segmentation-3-0"),
            ])
        elif os.path.isdir(seg_dir):
            search_dirs.append(os.path.join(seg_dir, "sherpa-onnx-pyannote-segmentation-3-0"))

        for sd in search_dirs:
            if not sd or not os.path.exists(sd):
                continue
            if os.path.isfile(sd) and sd.endswith(".onnx"):
                seg_model = sd
                break
            for cand in ["model.int8.onnx", "model.onnx"]:
                p = os.path.join(sd, cand)
                if os.path.isfile(p):
                    seg_model = p
                    break
            if seg_model:
                break

        if not seg_model:
            base_search = os.path.dirname(seg_dir) if os.path.isfile(seg_dir) else seg_dir
            for root, _, files in os.walk(base_search):
                for f in sorted(files):
                    if f in ("model.int8.onnx", "model.onnx") or (f.endswith(".onnx") and "segment" in f.lower()):
                        seg_model = os.path.join(root, f)
                        break
                if seg_model:
                    break

        if not seg_model:
            raise FileNotFoundError(
                f"Cannot find segmentation .onnx model in or near: {seg_dir}.\n"
                f"Please run 'termux-stt install --engine diarization' or in Python:\n"
                f"  from termux_stt.platform.installer import EngineInstaller\n"
                f"  EngineInstaller.install_diarization()"
            )

        return seg_model, emb_path

    @staticmethod
    def _load_audio_samples(wav_path: str) -> List[float]:
        """Load 16kHz mono WAV audio as a list of normalized float32 samples [-1.0, 1.0]."""
        import array
        import wave

        with wave.open(wav_path, "rb") as wf:
            sampwidth = wf.getsampwidth()
            num_frames = wf.getnframes()
            raw_pcm = wf.readframes(num_frames)

        if sampwidth == 2:
            pcm_samples = array.array("h", raw_pcm)
            return [s / 32768.0 for s in pcm_samples]
        elif sampwidth == 4:
            pcm_samples = array.array("i", raw_pcm)
            return [s / 2147483648.0 for s in pcm_samples]
        elif sampwidth == 1:
            pcm_samples = array.array("B", raw_pcm)
            return [(s - 128) / 128.0 for s in pcm_samples]
        else:
            raise ValueError(f"Unsupported WAV sample width: {sampwidth} bytes (must be 16-bit PCM)")

    def _determine_provider(self) -> str:
        """Determine ONNX runtime provider adhering to Strict OpenCL Protocol.

        Strict OpenCL Protocol:
        - OpenCL is enabled ONLY when explicitly declared by user (--device opencl).
        - Vulkan or GPU request defaults to vulkan or cpu NEON.
        - OpenCL is NEVER implicitly selected as a fallback.
        """
        if self.device == "opencl" or self.provider == "opencl":
            return "opencl"
        if self.device in ("vulkan", "gpu"):
            return "vulkan"
        return self.provider if self.provider in ("cpu", "cuda", "nnapi") else "cpu"

    def _diarize_in_process(
        self, wav_path: str, num_spk: Optional[int], seg_model: str, emb_path: str
    ) -> List[Tuple[float, float, int]]:
        """Tier 1: High-performance Python C-Extension In-Process Fastpath."""
        import sherpa_onnx

        num_threads = self.threads or min(os.cpu_count() or 4, 4)
        provider = self._determine_provider()

        logger.debug(
            "Initializing Tier 1 In-Process SherpaDiarizer (threads=%d, provider=%s, device=%s)",
            num_threads, provider, self.device
        )

        seg_pyannote = sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
            model=seg_model,
            window_shift_ratio=self.window_shift_ratio,
        )
        seg_cfg = sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=seg_pyannote,
            num_threads=num_threads,
            provider=provider,
        )
        emb_cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=emb_path,
            num_threads=num_threads,
            provider=provider,
        )
        if num_spk and num_spk > 0:
            cluster_cfg = sherpa_onnx.FastClusteringConfig(num_clusters=num_spk)
        else:
            cluster_cfg = sherpa_onnx.FastClusteringConfig(threshold=self.threshold)

        diar_cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=seg_cfg,
            embedding=emb_cfg,
            clustering=cluster_cfg,
        )
        diarizer = sherpa_onnx.OfflineSpeakerDiarization(diar_cfg)

        samples = self._load_audio_samples(wav_path)
        result = diarizer.process(samples)
        segments = result.sort_by_start_time()

        return [(float(seg.start), float(seg.end), int(seg.speaker)) for seg in segments]

    def _diarize_subprocess(
        self, wav_path: str, num_spk: Optional[int], seg_model: str, emb_path: str
    ) -> List[Tuple[float, float, int]]:
        """Tier 2: Subprocess Fallback via isolated C++ NDK binary."""
        binary = self._find_binary()
        num_threads = self.threads or min(os.cpu_count() or 4, 4)
        provider = self._determine_provider()

        cmd = [
            binary,
            f"--segmentation.pyannote-model={seg_model}",
            f"--embedding.model={emb_path}",
            f"--segmentation.num-threads={num_threads}",
            f"--embedding.num-threads={num_threads}",
            f"--segmentation.provider={provider}",
            f"--embedding.provider={provider}",
            f"--segmentation.pyannote-window-shift-ratio={self.window_shift_ratio}",
        ]

        if num_spk and num_spk > 0:
            cmd.append(f"--clustering.num-clusters={num_spk}")
        else:
            cmd.append(f"--clustering.threshold={self.threshold}")

        cmd.append(wav_path)

        # Configure environment for acceleration backend
        env = os.environ.copy()
        if self.device == "opencl" or provider == "opencl":
            # Explicit OpenCL declaration required by user protocol
            env["AMEVA_STT_BACKEND"] = "opencl"
            env["CL_CONTEXT_PLATFORM_DEVICE_TYPE"] = "GPU"
            env["CL_DEVICE_TYPE"] = "CL_DEVICE_TYPE_GPU"
            logger.info("Explicit OpenCL acceleration requested for diarization backend")
        elif self.device in ("vulkan", "gpu", "auto"):
            env["AMEVA_STT_BACKEND"] = "vulkan"

        logger.info("Executing sherpa speaker diarization subprocess: %s", " ".join(cmd))
        result = run_isolated(cmd, env=env)
        if result.returncode != 0:
            raise RuntimeError(
                f"sherpa-onnx-offline-speaker-diarization failed with exit code {result.returncode}: "
                f"{result.stderr}"
            )

        return self._parse_output(result.stdout)

    def diarize_audio(
        self, audio_path: str, num_speakers: Optional[int] = None
    ) -> List[Tuple[float, float, int]]:
        """Extract speaker intervals (start_sec, end_sec, speaker_id) from audio.

        Implements 2-Tier Accelerated Pipeline:
        - Tier 1: In-Process Python C-Extension (Zero process overhead, 4-thread NEON).
        - Tier 2: Subprocess C++ NDK Binary fallback (Fully isolated process pool).

        Returns
        -------
        List[Tuple[float, float, int]]
            List of (start, end, speaker_id) intervals.
        """
        num_spk = num_speakers if num_speakers is not None else self.num_speakers

        # 1. Preprocess audio to 16kHz mono WAV
        wav_path = preprocess(audio_path, target_sr=16000, force_mono=True)
        is_temp_wav = os.path.abspath(wav_path) != os.path.abspath(audio_path)

        try:
            # 2. Locate models
            seg_model, emb_path = self._resolve_models()

            # 3. Tier 1: Try In-Process Fastpath
            try:
                intervals = self._diarize_in_process(wav_path, num_spk, seg_model, emb_path)
                logger.info("Tier 1 In-Process diarization completed: %d intervals extracted", len(intervals))
                return intervals
            except (ImportError, ModuleNotFoundError) as mod_err:
                logger.debug("sherpa_onnx module not available (%s); falling back to Tier 2 subprocess", mod_err)
            except Exception as in_proc_err:
                logger.warning(
                    "Tier 1 In-Process diarization encountered error (%s); falling back to Tier 2 subprocess",
                    in_proc_err
                )

            # 4. Tier 2: Subprocess Fallback
            return self._diarize_subprocess(wav_path, num_spk, seg_model, emb_path)

        finally:
            if is_temp_wav and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

    @staticmethod
    def _parse_output(stdout: str) -> List[Tuple[float, float, int]]:
        """Parse sherpa-onnx speaker diarization stdout timestamps.

        Standard output format examples:
          start: 0.120, end: 3.450, speaker: 0
          or
          SPEAKER test 1 0.120 3.330 <NA> <NA> 0 <NA> <NA> (RTTM)
          or
          0.120 -- 3.450: speaker 0
        """
        intervals = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue

            # Format 1: start: 0.120, end: 3.450, speaker: 0
            m1 = re.search(r"start\s*:\s*([\d\.]+).*?end\s*:\s*([\d\.]+).*?speaker\s*:\s*(\d+)", line, re.IGNORECASE)
            if m1:
                start = float(m1.group(1))
                end = float(m1.group(2))
                spk = int(m1.group(3))
                intervals.append((start, end, spk))
                continue

            # Format 2: 0.120 -- 3.450: speaker 0 or 0.284 -- 2.107 speaker_00
            m2 = re.search(r"([\d\.]+)\s*(?:--|-|to)\s*([\d\.]+)\s*[:\s]*speaker_?(\d+)", line, re.IGNORECASE)
            if m2:
                start = float(m2.group(1))
                end = float(m2.group(2))
                spk = int(m2.group(3))
                intervals.append((start, end, spk))
                continue

            # Format 3: RTTM standard: SPEAKER <file> <channel> <start> <duration> <NA> <NA> <spk>
            parts = line.split()
            if len(parts) >= 8 and parts[0].upper() == "SPEAKER":
                try:
                    start = float(parts[3])
                    dur = float(parts[4])
                    spk_str = parts[7]
                    spk_id = int(re.sub(r"\D", "", spk_str)) if any(c.isdigit() for c in spk_str) else 0
                    intervals.append((start, start + dur, spk_id))
                except (ValueError, IndexError):
                    continue

        intervals.sort(key=lambda x: x[0])
        return intervals
