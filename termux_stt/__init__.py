# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
termux-stt - Android on-device STT & Neural Diarization framework for Termux.

Unified interface for Whisper.cpp (Vulkan GPU/CPU) and Sherpa-ONNX (SenseVoice)
with neural speaker diarization (PyAnnote 3.0 + CAM++ 192d) and TS-VAD overlap resolution.

Quick Start
-----------
>>> from termux_stt import create_engine
>>> engine = create_engine("whisper", model="small", lang="ko")
>>> result = engine.transcribe("meeting.wav")
>>> print(result.text)
"""

__version__ = "2.1.0"
__author__ = 'Eunho Kim (@uno-km)'


def create_engine(
    engine: str = "whisper",
    *,
    model: str = None,
    lang: str = "ko",
    device: str = "auto",
    num_speakers: int = 0,
    threads: int = None,
    vad: bool = True,
    vad_threshold: float = 0.5,
    quantization: str = "q5_1",
    custom_model_path: str = None,
    **kwargs,
):
    """Create an STT engine instance.

    Parameters
    ----------
    engine : str
        ``"whisper"`` | ``"vosk"`` | ``"sherpa"`` | ``"hybrid"``
    model : str, optional
        ``"tiny"`` | ``"base"`` | ``"small"`` | ``"medium"`` | ``"custom"``
    lang : str
        ISO 639-1 language code. Default ``"ko"``.
    num_speakers : int
        ``0`` = no diarization, ``2+`` = enable speaker diarization.
    threads : int, optional
        CPU thread count. ``None`` = auto-detect big-cores.
    vad : bool
        Enable Silero-VAD silence filtering. Default ``True``.
    vad_threshold : float
        VAD sensitivity (0.0??.0). Default ``0.5``.
    quantization : str
        GGML quantization: ``"f16"`` | ``"q8_0"`` | ``"q5_1"`` | ``"q4_0"``.
    custom_model_path : str, optional
        Path to a custom fine-tuned model.
    **kwargs
        Additional engine-specific options.

    Returns
    -------
    Engine
        A ready-to-use engine instance with ``transcribe()``,
        ``stream_mic()``, ``diarize()``, and more.

    Examples
    --------
    >>> engine = create_engine("whisper", model="base", lang="ko")
    >>> result = engine.transcribe("meeting.wav")

    >>> engine = create_engine("hybrid", lang="ko", num_speakers=2)
    >>> result = engine.diarize("interview.wav")
    """
    from .engine import EngineRegistry

    return EngineRegistry.get_engine(
        engine,
        model=model,
        lang=lang,
        device=device,
        num_speakers=num_speakers,
        threads=threads,
        vad=vad,
        vad_threshold=vad_threshold,
        quantization=quantization,
        custom_model_path=custom_model_path,
        **kwargs,
    )


# Standard Unified Factory Alias
load = create_engine


def transcribe(audio_path: str, model: str = "base", lang: str = "ko", **kwargs):
    """One-shot direct transcription helper."""
    engine = load(model=model, lang=lang, **kwargs)
    return engine.transcribe(audio_path)


from .exceptions import (
    AmevaTermuxError,
    ErrorCode,
    ExitCode,
    TermuxSTTError,
    PlatformNotSupportedError,
    ModelNotFoundError,
    HardwareCompatibilityError,
    RuntimeNotFoundError,
    ProvisioningError,
    AudioProcessingError,
    InferenceTimeoutError,
    ClusterConnectionError,
    ClusterConfigurationError,
)
from . import cluster
from .cluster import (
    parse_cluster_rpc_spec,
    verify_rpc_cluster_nodes,
    verify_rpc_cluster_health,
)
from .hardware import detect_hardware, HardwareProfile, resolve_device, is_termux, is_android
from .downloader import download_model, resolve_model_path, list_models

__all__ = [
    'create_engine',
    'load',
    'transcribe',
    '__version__',
    '__author__',
    'AmevaTermuxError',
    'ErrorCode',
    'ExitCode',
    'TermuxSTTError',
    'PlatformNotSupportedError',
    'ModelNotFoundError',
    'HardwareCompatibilityError',
    'RuntimeNotFoundError',
    'ProvisioningError',
    'AudioProcessingError',
    'InferenceTimeoutError',
    'ClusterConnectionError',
    'ClusterConfigurationError',
    'cluster',
    'parse_cluster_rpc_spec',
    'verify_rpc_cluster_nodes',
    'verify_rpc_cluster_health',
    'detect_hardware',
    'HardwareProfile',
    'resolve_device',
    'is_termux',
    'is_android',
    'download_model',
    'resolve_model_path',
    'list_models',
]



