# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Voice Activity Detection (VAD) module.
Provides Silero-VAD and EnergyVAD fallback.
"""

import logging
import math
import os
import struct
import subprocess
import tempfile
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

__all__ = ["VADResult", "BaseVAD", "SileroVAD", "EnergyVAD", "detect_speech", "split_by_speech"]

@dataclass
class VADResult:
    segments: List[Tuple[float, float]]
    speech_ratio: float

class BaseVAD(ABC):
    @abstractmethod
    def process(self, audio_path: str, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 100) -> VADResult:
        pass

class EnergyVAD(BaseVAD):
    def process(self, audio_path: str, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 100) -> VADResult:
        """Simple pure Python energy-based VAD as fallback."""
        with wave.open(audio_path, 'rb') as wf:
            framerate = wf.getframerate()
            nframes = wf.getnframes()
            audio_data = wf.readframes(nframes)

            samples = struct.unpack(f"<{nframes}h", audio_data)

        # Simplified framing and energy thresholding
        frame_ms = 30
        frame_size = int(framerate * frame_ms / 1000)

        segments = []
        in_speech = False
        start_time = 0.0

        for i in range(0, len(samples), frame_size):
            frame = samples[i:i+frame_size]
            if not frame:
                break

            energy = sum(x*x for x in frame) / len(frame)
            rms = math.sqrt(energy) if energy > 0 else 0

            current_time = i / framerate
            # Heuristic threshold
            if rms > threshold * 1000:
                if not in_speech:
                    in_speech = True
                    start_time = current_time
            else:
                if in_speech:
                    in_speech = False
                    end_time = current_time
                    if (end_time - start_time) * 1000 >= min_speech_ms:
                        segments.append((start_time, end_time))

        total_duration = nframes / framerate
        speech_duration = sum(e - s for s, e in segments)
        speech_ratio = speech_duration / total_duration if total_duration > 0 else 0.0

        return VADResult(segments=segments, speech_ratio=speech_ratio)

class SileroVAD(BaseVAD):
    """Silero-VAD inference engine using ONNX Runtime when available."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._session = None

    def _init_session(self):
        if self._session is not None:
            return
        import onnxruntime as ort
        if not self.model_path or not os.path.exists(self.model_path):
            from termux_stt.models.hub import ModelHub
            self.model_path = ModelHub.ensure_model("sherpa", "silero-vad")
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 2
        self._session = ort.InferenceSession(self.model_path, sess_options=opts)

    def process(self, audio_path: str, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 100) -> VADResult:
        try:
            import numpy as np
            self._init_session()

            with wave.open(audio_path, 'rb') as wf:
                sr = wf.getframerate()
                nframes = wf.getnframes()
                data = wf.readframes(nframes)
                samples = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0

            window_size_samples = 512 if sr == 16000 else 256
            state = np.zeros((2, 1, 128), dtype=np.float32)
            sr_tensor = np.array(sr, dtype=np.int64)

            segments = []
            in_speech = False
            start_sec = 0.0

            for i in range(0, len(samples) - window_size_samples, window_size_samples):
                chunk = samples[i:i + window_size_samples][np.newaxis, :]
                ort_inputs = {
                    'input': chunk,
                    'state': state,
                    'sr': sr_tensor
                }
                out, state = self._session.run(None, ort_inputs)
                prob = float(out[0][0])
                current_sec = i / float(sr)

                if prob >= threshold:
                    if not in_speech:
                        in_speech = True
                        start_sec = current_sec
                else:
                    if in_speech:
                        in_speech = False
                        end_sec = current_sec
                        if (end_sec - start_sec) * 1000 >= min_speech_ms:
                            segments.append((start_sec, end_sec))

            if in_speech:
                end_sec = len(samples) / float(sr)
                if (end_sec - start_sec) * 1000 >= min_speech_ms:
                    segments.append((start_sec, end_sec))

            total_dur = len(samples) / float(sr) if sr > 0 else 1.0
            speech_ratio = sum(e - s for s, e in segments) / total_dur if total_dur > 0 else 0.0
            return VADResult(segments=segments, speech_ratio=speech_ratio)

        except Exception as exc:
            import logging
            logging.getLogger("termux_stt.audio.vad").warning(
                "Silero-VAD ONNX processing failed (%s). Falling back to EnergyVAD.", exc
            )
            return EnergyVAD().process(audio_path, threshold, min_speech_ms, min_silence_ms)

logger = logging.getLogger(__name__)


def detect_speech(audio_path: str, threshold: float = 0.5, min_speech_ms: int = 250, min_silence_ms: int = 100, use_silero: bool = False) -> VADResult:
    """Detect speech segments using EnergyVAD or SileroVAD."""
    if use_silero:
        vad = SileroVAD()
    else:
        vad = EnergyVAD()
    return vad.process(audio_path, threshold, min_speech_ms, min_silence_ms)


def split_by_speech(audio_path: str, vad_result: VADResult) -> List[str]:
    """Split audio into temporary files based on VAD segments.

    Raises
    ------
    RuntimeError
        If ffmpeg execution fails to split audio segments.
    """
    output_files = []
    for idx, (start, end) in enumerate(vad_result.segments):
        fd, out_path = tempfile.mkstemp(suffix=f"_seg_{idx}.wav", prefix="vad_")
        os.close(fd)

        cmd = [
            "ffmpeg",
            "-y",
            "-i", audio_path,
            "-ss", f"{start:.3f}",
            "-to", f"{end:.3f}",
            "-c:a", "pcm_s16le",
            out_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            output_files.append(out_path)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else str(e)
            logger.error("FFmpeg segmentation failed for segment %d [%.3f - %.3f]: %s", idx, start, end, stderr)
            # Cleanup any already created temporary files
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError as rm_err:
                    logger.debug("Failed removing out_path %s: %s", out_path, rm_err)
            for f in output_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except OSError as rm_err:
                        logger.debug("Failed removing segment file %s: %s", f, rm_err)
            raise RuntimeError(f"FFmpeg segmentation failed on segment {idx} [{start:.3f}-{end:.3f}]: {stderr}") from e
        except Exception as e:
            logger.error("Unexpected error splitting segment %d [%.3f - %.3f]: %s", idx, start, end, e)
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError as rm_err:
                    logger.debug("Failed removing out_path %s: %s", out_path, rm_err)
            for f in output_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except OSError as rm_err:
                        logger.debug("Failed removing segment file %s: %s", f, rm_err)
            raise RuntimeError(f"Unexpected error splitting audio: {e}") from e

    return output_files
