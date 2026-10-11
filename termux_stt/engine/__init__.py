# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import logging
from typing import Any, Dict, Type

from .base import Engine, EngineConfig

logger = logging.getLogger(__name__)

__all__ = ['EngineRegistry', 'Engine', 'EngineConfig']


class EngineRegistry:
    """Registry that maps engine names to their concrete Engine subclasses.

    Supported engine names:
        - ``"whisper"`` — whisper.cpp subprocess wrapper (Vulkan GPU/CPU)
        - ``"sherpa"``  — Sherpa-ONNX subprocess wrapper (SenseVoice / Conformer)
        - ``"hybrid"``  — PyAnnote 3.0 + CAM++ 192d Diarization + Whisper STT hybrid pipeline
    """

    _engines: Dict[str, Type[Engine]] = {}
    _engine_import_errors: Dict[str, Exception] = {}

    @classmethod
    def register(cls, name: str, engine_class: Type[Engine]) -> None:
        """Register an engine class under *name*."""
        cls._engines[name] = engine_class
        cls._engine_import_errors.pop(name, None)

    @classmethod
    def get_engine(cls, engine_name: str, **kwargs: Any) -> Engine:
        """Instantiate and return the engine identified by *engine_name*.

        Parameters
        ----------
        engine_name : str
            One of ``"whisper"``, ``"vosk"``, ``"sherpa"``, ``"hybrid"``.
        **kwargs
            Forwarded to the engine constructor via :class:`EngineConfig`.

        Returns
        -------
        Engine
            A ready-to-use engine instance.

        Raises
        ------
        RuntimeError
            If *engine_name* failed to load due to an internal import/initialization error.
        ValueError
            If *engine_name* is not registered or unknown.
        """
        # Lazy-import concrete engines to avoid circular imports
        cls._ensure_builtin_engines()

        name_lower = engine_name.lower()
        if name_lower == "vosk":
            raise ValueError(
                "Engine 'vosk' has been deprecated and completely removed in v2.0.0. "
                "Please use 'sherpa' (SenseVoice non-autoregressive ultra-fast STT) or 'whisper'."
            )
        if name_lower not in cls._engines:
            if name_lower in cls._engine_import_errors:
                cause = cls._engine_import_errors[name_lower]
                raise RuntimeError(
                    f"Engine '{engine_name}' is supported but failed to load due to an import/initialization error: {cause}"
                ) from cause

            available = ', '.join(sorted(cls._engines.keys())) or '(none)'
            raise ValueError(
                f"Unknown engine '{engine_name}'. "
                f"Available engines: {available}"
            )

        engine_cls = cls._engines[name_lower]

        # Build EngineConfig from kwargs
        config = EngineConfig(
            engine=name_lower,
            model=kwargs.pop('model', None),
            lang=kwargs.pop('lang', 'ko'),
            device=kwargs.pop('device', 'auto'),
            threads=kwargs.pop('threads', None),
            vad=kwargs.pop('vad', True),
            vad_threshold=kwargs.pop('vad_threshold', 0.5),
            quantization=kwargs.pop('quantization', 'q5_1'),
            num_speakers=kwargs.pop('num_speakers', 0),
            custom_model_path=kwargs.pop('custom_model_path', None),
            extra=kwargs,
        )

        return engine_cls(config)

    @classmethod
    def list_engines(cls) -> list:
        """Return a list of registered engine names."""
        cls._ensure_builtin_engines()
        return sorted(cls._engines.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    _builtins_loaded: bool = False

    @classmethod
    def _ensure_builtin_engines(cls) -> None:
        """Lazily register built-in engines while capturing import errors."""
        if cls._builtins_loaded:
            return
        cls._builtins_loaded = True

        try:
            from .whisper_engine import WhisperEngine
            cls.register('whisper', WhisperEngine)
        except Exception as exc:
            logger.debug("Failed to register builtin engine 'whisper': %s", exc)
            cls._engine_import_errors['whisper'] = exc

        try:
            from .sherpa_engine import SherpaEngine
            cls.register('sherpa', SherpaEngine)
        except Exception as exc:
            logger.debug("Failed to register builtin engine 'sherpa': %s", exc)
            cls._engine_import_errors['sherpa'] = exc

        try:
            from .hybrid_engine import HybridEngine
            cls.register('hybrid', HybridEngine)
        except Exception as exc:
            logger.debug("Failed to register builtin engine 'hybrid': %s", exc)
            cls._engine_import_errors['hybrid'] = exc
