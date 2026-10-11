# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Abstract base classes for STT engines.

Every concrete engine (Whisper, Vosk, Sherpa, Hybrid) inherits from
:class:`Engine` and implements its abstract methods.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from ..export.result import DiarizedResult, Segment, TranscriptResult

__all__ = ['Engine', 'EngineConfig']


@dataclass
class EngineConfig:
    engine: str = 'whisper'
    model: Optional[str] = None
    lang: str = 'ko'
    device: Any = 'auto'
    threads: Optional[int] = None
    vad: bool = True
    vad_threshold: float = 0.5
    quantization: str = 'q5_1'
    num_speakers: int = 0
    custom_model_path: Optional[str] = None
    cluster_rpc_servers: Optional[Any] = None
    cluster_split_mode: Optional[str] = None
    cluster_tensor_split: Optional[str] = None
    cluster_vram_budget: Optional[Dict[str, int]] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        engine: str = 'whisper',
        model: Optional[str] = None,
        lang: str = 'ko',
        device: Any = 'auto',
        threads: Optional[int] = None,
        vad: bool = True,
        vad_threshold: float = 0.5,
        quantization: str = 'q5_1',
        num_speakers: int = 0,
        custom_model_path: Optional[str] = None,
        cluster_rpc_servers: Optional[Any] = None,
        cluster_split_mode: Optional[str] = None,
        cluster_tensor_split: Optional[str] = None,
        cluster_vram_budget: Optional[Dict[str, int]] = None,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        self.engine = engine
        self.model = model or kwargs.get('model_path') or kwargs.get('model_name')
        self.lang = lang if lang != 'ko' or 'language' not in kwargs else kwargs.get('language', 'ko')
        self.device = device if 'device' not in kwargs else kwargs.get('device', 'auto')
        self.threads = threads if threads is not None else kwargs.get('num_threads')
        self.vad = vad if 'use_vad' not in kwargs else kwargs.get('use_vad', True)
        self.vad_threshold = vad_threshold
        self.quantization = quantization
        self.num_speakers = num_speakers
        self.custom_model_path = custom_model_path or kwargs.get('custom_model_path')
        self.cluster_rpc_servers = cluster_rpc_servers or kwargs.get('cluster_rpc_servers') or kwargs.get('rpc')
        self.cluster_split_mode = cluster_split_mode or kwargs.get('cluster_split_mode')
        self.cluster_tensor_split = cluster_tensor_split or kwargs.get('cluster_tensor_split') or kwargs.get('tensor_split')
        self.cluster_vram_budget = cluster_vram_budget or kwargs.get('cluster_vram_budget')
        self.extra = extra or {}
        if self.cluster_rpc_servers:
            self.extra['cluster_rpc_servers'] = self.cluster_rpc_servers
            self.extra['rpc'] = self.cluster_rpc_servers
        if self.cluster_split_mode:
            self.extra['cluster_split_mode'] = self.cluster_split_mode
        if self.cluster_tensor_split:
            self.extra['cluster_tensor_split'] = self.cluster_tensor_split
            self.extra['tensor_split'] = self.cluster_tensor_split
        if self.cluster_vram_budget:
            self.extra['cluster_vram_budget'] = self.cluster_vram_budget
        # Merge remaining kwargs into extra
        for k, v in kwargs.items():
            if k not in {'model_path', 'model_name', 'language', 'num_threads', 'use_vad', 'device', 'cluster_rpc_servers', 'cluster_split_mode', 'cluster_tensor_split', 'cluster_vram_budget'}:
                self.extra[k] = v

    # Convenience helpers ---------------------------------------------------

    @property
    def model_name(self) -> str:
        """Return the model name, falling back to engine-specific defaults."""
        if self.model:
            return self.model
        defaults = {
            'whisper': 'base',
            'vosk': 'small-ko-0.22',
            'sherpa': 'sensevoice-small',
            'hybrid': 'base',
        }
        return defaults.get(self.engine, 'base')

    @property
    def language(self) -> str:
        """Alias for ``lang``."""
        return self.lang


class Engine(ABC):
    """Abstract Base Class for all STT engines.

    Every engine must implement the five core methods below.  The
    ``create_engine()`` factory (in ``termux_stt.__init__``) constructs the
    appropriate subclass, so callers never need to instantiate engines
    directly.

    Example
    -------
    >>> from termux_stt import create_engine
    >>> engine = create_engine("whisper", model="base", lang="ko")
    >>> result = engine.transcribe("meeting.wav")
    >>> print(result.text)
    """

    @abstractmethod
    def transcribe(self, audio_path: str, **kwargs: Any) -> TranscriptResult:
        """Transcribe an audio file and return the full result.

        Parameters
        ----------
        audio_path : str
            Path to an audio file (any format supported by ffmpeg).
        **kwargs
            Engine-specific options.

        Returns
        -------
        TranscriptResult
            Object containing *text*, *segments*, *language*, and *duration*.
        """

    @abstractmethod
    def stream_mic(
        self, duration: Optional[float] = None
    ) -> Iterator[Segment]:
        """Stream transcription from the device microphone.

        Yields :class:`Segment` objects as speech is detected.
        """

    @abstractmethod
    def stream_file(
        self, audio_path: str, chunk_sec: float = 5.0
    ) -> Iterator[Segment]:
        """Stream transcription from a file in chunks.

        Useful for very long recordings where holding the entire result
        in memory is undesirable.
        """

    @abstractmethod
    def diarize(
        self, audio_path: str, num_speakers: int = 2
    ) -> DiarizedResult:
        """Run STT **and** speaker diarization.

        Parameters
        ----------
        audio_path : str
            Path to the audio file.
        num_speakers : int
            Expected number of distinct speakers.

        Returns
        -------
        DiarizedResult
            Extends :class:`TranscriptResult` with per-segment speaker
            labels.
        """

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Return a dictionary of engine / model / hardware status info."""
