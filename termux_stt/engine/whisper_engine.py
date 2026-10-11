# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""Whisper.cpp engine wrapper ??subprocess-isolated STT for Android Termux.

Runs ``whisper.cpp`` as an external process for crash isolation; a C++
segfault will never take down the Python host.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from termux_stt.engine.base import Engine, EngineConfig
from termux_stt.export.result import DiarizedResult, Segment, TranscriptResult
from termux_stt.platform.process_pool import run_isolated
from termux_stt.cluster import parse_cluster_rpc_spec, verify_rpc_cluster_nodes

logger = logging.getLogger(__name__)

__all__ = ['WhisperEngine']


class WhisperEngine(Engine):
    """whisper.cpp engine via subprocess with process isolation.

    Supports all GGML quantisation levels (f16, q8_0, q5_1, q4_0) and
    automatic ARM NEON / FP16 optimisation.
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.model = config.model_name
        self.lang = config.language
        self.device = config.device

        # Hardware acceleration context delegation via ameva-runtime & SmartRouter
        dev_lower = str(self.device or "auto").strip().lower()
        self.ctx = None
        self.runtime = None
        self.router = None
        if dev_lower != "cpu":
            try:
                from ameva_runtime.core import get_runtime
                from ameva_runtime.router import SmartRouter

                self.runtime = get_runtime()
                self.router = SmartRouter(self.runtime.profile)
            except ImportError as imp_err:
                from termux_stt.hardware import _note_cpu_instead, _require_gpu_runtime
                if dev_lower in ("vulkan", "gpu", "opencl"):
                    _require_gpu_runtime(dev_lower)  # runtime missing or too old: the shared explanation
                    from termux_stt.exceptions import PlatformNotSupportedError, ErrorCode
                    raise PlatformNotSupportedError(
                        f"[ERROR: AMEVA-STT-E002] ameva-runtime is installed but its core modules failed to import: {imp_err}",
                        code=ErrorCode.VULKAN_DEVICE,
                    ) from imp_err
                _note_cpu_instead("ameva-runtime (AMUDA) is not installed")
                self.device = "cpu"
            except Exception as exc:
                from termux_stt.exceptions import TermuxSTTError, PlatformNotSupportedError, ErrorCode
                if isinstance(exc, TermuxSTTError):
                    raise
                raise PlatformNotSupportedError(
                    f"[ERROR: AMEVA-STT-E002] Failed to initialize ameva-runtime for WhisperEngine: {exc}",
                    code=ErrorCode.VULKAN_DEVICE,
                ) from exc

        # Lazy-import to avoid circular deps at module load time
        try:
            from termux_stt.hardware import get_optimal_threads
            self.threads = config.threads or get_optimal_threads()
        except Exception:
            self.threads = config.threads or 4

    # ------------------------------------------------------------------
    # Binary location
    # ------------------------------------------------------------------

    def _get_binary_path(self) -> str:
        """Locate the ``whisper.cpp`` binary (whisper-cli or whisper-cpp)."""
        import shutil
        searched_paths = []
        # 1. Canonical AMEVA Hardware-Accelerated STT binaries (Highest Priority)
        ameva_candidates = [
            Path.home() / ".local" / "share" / "ameva" / "rpc_llama" / "bin" / "whisper-cli",
            Path.home() / ".local" / "share" / "ameva" / "current" / "stt" / "bin" / "whisper-cli",
            Path("/data/data/com.termux/files/home/.local/share/ameva/current/stt/bin/whisper-cli"),
            Path.home() / ".local" / "bin" / "whisper-cli",
            Path("/data/data/com.termux/files/home/.local/bin/whisper-cli"),
        ]
        for p in ameva_candidates:
            searched_paths.append(str(p))
            if p.exists() and (os.access(str(p), os.X_OK) or os.name == "nt"):
                return str(p)

        # 2. System PATH lookup
        for name in ["whisper-cli", "whisper-cpp", "main"]:
            found = shutil.which(name)
            if found and (os.access(found, os.X_OK) or os.name == "nt"):
                return found
            searched_paths.append(f"PATH:{name}")

        prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
        candidates = [
            Path(prefix) / "bin" / "whisper-cli",
            Path(prefix) / "bin" / "whisper-cpp",
            Path.home() / ".local" / "bin" / "whisper-cpp",
            Path("/data/data/com.termux/files/home/.local/bin/whisper-cpp"),
            Path("/usr/local/bin/whisper-cli"),
            Path("/usr/local/bin/whisper-cpp"),
        ]
        for p in candidates:
            searched_paths.append(str(p))
            if p.exists() and (os.access(str(p), os.X_OK) or os.name == "nt"):
                return str(p)

        # Raise informative error if not found in any candidate path
        searched_fmt = "\n  - ".join(searched_paths)
        raise FileNotFoundError(
            f"Cannot locate 'whisper.cpp' runtime executable (whisper-cli or whisper-cpp).\n"
            f"Searched candidate locations:\n  - {searched_fmt}\n\n"
            f"Action Required:\n"
            f"  1. Run automatic installer: termux-stt install\n"
            f"  2. Or install manually via Termux: pkg install whisper.cpp\n"
            f"  3. Or compile whisper.cpp and add to PATH: export PATH=$HOME/.local/bin:$PATH"
        )

    @classmethod
    def _supports_gpu(cls, binary_path: str) -> dict:
        """Inspects whether the target whisper-cli binary supports GPU offload flags (-ngl, -dev, -ng)."""
        if not hasattr(cls, "_gpu_flags_cache"):
            cls._gpu_flags_cache = {}
        if binary_path in cls._gpu_flags_cache:
            return cls._gpu_flags_cache[binary_path]
        try:
            from ameva_runtime.adapters.stt import SttAdapter
            check_env = SttAdapter.get_execution_environment(base_env=os.environ.copy())
        except Exception:
            check_env = os.environ.copy()
        if "LD_LIBRARY_PATH" in check_env:
            prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
            prefix_lib = f"{prefix}/lib"
            parts = [p for p in check_env["LD_LIBRARY_PATH"].split(":") if p and p != prefix_lib]
            check_env["LD_LIBRARY_PATH"] = ":".join(parts)

        try:
            res = run_isolated([binary_path, "-h"], env=check_env)
            help_text = (res.stdout or "") + (res.stderr or "")
            flags = {
                "ngl": "-ngl" in help_text or "--gpu-layers" in help_text,
                "dev": "-dev" in help_text or "--device" in help_text,
                "no_gpu": "-ng" in help_text or "--no-gpu" in help_text,
                "split_mode": "-sm" in help_text or "--split-mode" in help_text or "--optimize-gpu-cpu" in help_text,
            }
            flags["supports_gpu"] = flags["ngl"] or flags["dev"] or flags["no_gpu"]
            if "ameva" in binary_path and not flags["supports_gpu"]:
                flags["dev"] = True
                flags["supports_gpu"] = True
            cls._gpu_flags_cache[binary_path] = flags
            return flags
        except Exception:
            flags = {"ngl": False, "dev": False, "no_gpu": False, "supports_gpu": False}
            cls._gpu_flags_cache[binary_path] = flags
            return flags

    @classmethod
    def _supports_ngl(cls, binary_path: str) -> bool:
        """Inspects whether the target whisper-cli binary supports GPU offload flags (-ngl or -dev)."""
        return cls._supports_gpu(binary_path)["supports_gpu"]

    def _prepare_env(self, device: str = "auto") -> Dict[str, str]:
        """
        Configure subprocess environment safely using ameva-runtime and Android Bionic ICD.

        Args:
            device: 'auto' (Vulkan priority with CPU fallback), 'vulkan' / 'gpu' (strict GPU fail-fast), 'cpu' (pure NEON).

        Returns:
            Dict[str, str]: Prepared environment dictionary with verified LD_LIBRARY_PATH and vendor quirks.
        """
        import sys
        from termux_stt.exceptions import PlatformNotSupportedError, ErrorCode

        env = os.environ.copy()
        dev_mode = str(device or "auto").strip().lower()

        if dev_mode == "cpu" or sys.platform == "win32":
            return env

        if dev_mode in ("vulkan", "gpu"):
            from termux_stt.hardware import _require_gpu_runtime
            _require_gpu_runtime(dev_mode)
        try:
            from ameva_runtime.adapters import SttAdapter
            adapter = SttAdapter()
            env = adapter.get_execution_environment(base_env=env)

            # Verify GPU status for explicit mode
            if dev_mode in ("vulkan", "gpu"):
                from ameva_runtime import vulkan as avr
                if hasattr(avr, "create_context"):
                    ctx = avr.create_context(dev_mode)
                elif hasattr(avr, "get_or_create_context"):
                    ctx = avr.get_or_create_context(dev_mode)
                else:
                    ctx = avr.VulkanContext(dev_mode)

                if ctx.backend_type != "vulkan" and not getattr(ctx, "is_gpu", False):
                    raise PlatformNotSupportedError(
                        f"[ERROR: AMEVA-STT-E002] Explicit Vulkan backend requested ('--device {device}'), but ameva-runtime "
                        f"initialized with non-GPU backend ('{ctx.backend_type}').",
                        code=ErrorCode.VULKAN_DEVICE,
                    )
        except ImportError as imp_err:
            if dev_mode in ("vulkan", "gpu"):
                raise PlatformNotSupportedError(
                    "[ERROR: AMEVA-STT-E001] GPU acceleration requires 'ameva-runtime'.\n"
                    "Cause: Hardware abstraction provider 'ameva-runtime' is not installed.\n"
                    "Action Required: Install the hardware acceleration package via:\n"
                    "  - Python: pip install ameva-runtime\n"
                    "  - Node.js: npm install @unokm/ameva-runtime\n"
                    "Documentation: https://github.com/uno-km/termux-stt",
                    code=ErrorCode.RUNTIME_NOT_INSTALLED,
                ) from imp_err
        except Exception as e:
            if dev_mode in ("vulkan", "gpu"):
                if isinstance(e, PlatformNotSupportedError):
                    raise
                raise PlatformNotSupportedError(
                    f"[ERROR: AMEVA-STT-E002] AMEVA Vulkan Runtime initialization failed: {e}",
                    code=ErrorCode.VULKAN_DEVICE,
                ) from e

        # Sanitize LD_LIBRARY_PATH: whisper-cli is self-contained with $ORIGIN and bundled libs.
        # Injecting Termux /usr/lib causes severe Bionic linker symbol collisions (e.g. libunwindstack Xzs_Construct on Android 15 / S25).
        if "LD_LIBRARY_PATH" in env:
            filtered_paths = [p for p in env["LD_LIBRARY_PATH"].split(":") if p and not p.endswith("/usr/lib")]
            env["LD_LIBRARY_PATH"] = ":".join(filtered_paths)

        return env


    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    def _parse_whisper_json(self, json_str: str) -> List[Segment]:
        """Parse ``whisper.cpp --output-json`` output into Segment list."""
        segments: List[Segment] = []
        try:
            data = json.loads(json_str)
            for seg in data.get("transcription", []):
                offsets = seg.get("offsets", {})
                if isinstance(offsets, dict):
                    t0 = offsets.get("from", 0) / 1000.0
                    t1 = offsets.get("to", 0) / 1000.0
                else:
                    t0, t1 = 0.0, 0.0
                text = seg.get("text", "").strip()
                if text:
                    segments.append(Segment(start=t0, end=t1, text=text))
        except Exception as exc:
            logger.error("Failed to parse whisper.cpp JSON output: %s", exc)
        return segments

    # ------------------------------------------------------------------
    # Core engine methods
    # ------------------------------------------------------------------

    def transcribe(self, audio_path: str, **kwargs: Any) -> TranscriptResult:
        """Transcribe an audio file using whisper.cpp."""
        from termux_stt.audio.preprocessor import preprocess, ensure_wav_format
        from termux_stt.models.hub import ModelHub
        from termux_stt.hardware import is_termux
        from termux_stt.platform.process_pool import run_isolated

        # 1. Ensure 16 kHz mono WAV format (avoids ffmpeg if already valid)
        wav_path = ensure_wav_format(audio_path)
        is_temp_wav = os.path.abspath(wav_path) != os.path.abspath(audio_path)

        try:
            # 2. Ensure model is downloaded
            model_path = ModelHub.ensure_model('whisper', self.model)

            # 3. Build command with all whisper.cpp control flags
            binary = self._get_binary_path()
            cmd = [
                binary,
                "-m", model_path,
                "-l", self.lang,
                "-t", str(self.threads),
                "-oj",  # output JSON
                "-f", wav_path,
            ]

            # Extract options from kwargs or self.config.extra
            opts = {**self.config.extra, **kwargs}

            if "prompt" in opts or "initial_prompt" in opts:
                prompt_val = opts.get("prompt") or opts.get("initial_prompt")
                cmd.extend(["--prompt", str(prompt_val)])
            # Production default: Greedy search (-bs 1) for mobile stability unless explicitly specified
            beam_sz = opts.get("beam_size")
            if beam_sz is None:
                beam_sz = 1
            cmd.extend(["-bs", str(beam_sz)])
            if "best_of" in opts:
                cmd.extend(["-bo", str(opts["best_of"])])
            if "temperature" in opts:
                cmd.extend(["-tp", str(opts["temperature"])])
            if opts.get("translate", False):
                cmd.append("-tr")
            if "max_len" in opts:
                cmd.extend(["-ml", str(opts["max_len"])])
            if opts.get("split_on_word", False):
                cmd.append("-sow")
            # Default to no_fallback on Termux unless explicitly disabled
            if opts.get("no_fallback", is_termux()):
                cmd.append("-nf")
            if "suppress_regex" in opts:
                cmd.extend(["--suppress-regex", str(opts["suppress_regex"])])
            if "grammar" in opts:
                cmd.extend(["--grammar", str(opts["grammar"])])
            if opts.get("dtw", False):
                cmd.append("-dtw")

            # Cluster Distributed Inference Routing & Pre-Flight Verification
            cluster_rpc = opts.get("cluster_rpc_servers") or opts.get("rpc")
            if cluster_rpc:
                parsed_servers = parse_cluster_rpc_spec(cluster_rpc)
                if parsed_servers:
                    verify_rpc_cluster_nodes(parsed_servers)
                    cmd.extend(["--rpc", ",".join(parsed_servers)])

            cluster_ts = opts.get("cluster_tensor_split") or opts.get("tensor_split")
            if cluster_ts:
                cmd.extend(["--tensor-split", str(cluster_ts).strip()])

            # Hardware Acceleration Routing via ameva-runtime & SmartRouter
            dev_lower = str(self.device or "auto").strip().lower()
            if dev_lower != "cpu":
                if not self._supports_ngl(binary):
                    raise RuntimeError(
                        f"[ZeroSilentFallback] Explicit Vulkan GPU mode requested ('{self.device}'), "
                        f"but whisper-cli binary at '{binary}' does not support GPU offload (-ngl). "
                        f"CPU fallback is strictly forbidden under Zero-Silent-Fallback protocol."
                    )
                try:
                    from ameva_runtime.core import get_runtime
                    from ameva_runtime.router import SmartRouter
                    from ameva_runtime.adapters.stt import SttAdapter

                    runtime = getattr(self, "runtime", None) or get_runtime()
                    router = getattr(self, "router", None) or SmartRouter(runtime.profile)
                    split_mode_req = opts.get("split_mode", True)
                    if opts.get("optimize_1", False):
                        self.threads = 1
                        split_mode_req = True

                    plan = router.route_for_stt(
                        model_name_or_path=self.model or "",
                        requested_backend="vulkan" if dev_lower in ("gpu", "vulkan") else None,
                        requested_threads=self.threads,
                        split_mode=split_mode_req,
                    )

                    # Bind optimal hardware flags (-dev 0, -sm, -t 4) directly from SmartRouter
                    flags_to_add = list(plan.cli_flags)
                    if not self._supports_gpu(binary).get("split_mode", False):
                        flags_to_add = [f for f in flags_to_add if f != "-sm"]
                    if "-t" in flags_to_add:
                        t_idx = flags_to_add.index("-t")
                        new_t = flags_to_add[t_idx + 1]
                        if "-t" in cmd:
                            cmd_t_idx = cmd.index("-t")
                            cmd[cmd_t_idx + 1] = new_t
                            flags_to_add = flags_to_add[:t_idx] + flags_to_add[t_idx + 2:]
                    cmd.extend(flags_to_add)
                    if "-nf" not in cmd and is_termux():
                        cmd.append("-nf")

                    # Golden Link Order environment & hardware quirks
                    run_env = SttAdapter.get_execution_environment(base_env=os.environ.copy())
                    if "LD_LIBRARY_PATH" in run_env:
                        prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
                        prefix_lib = f"{prefix}/lib"
                        parts = [p for p in run_env["LD_LIBRARY_PATH"].split(":") if p and p != prefix_lib]
                        run_env["LD_LIBRARY_PATH"] = ":".join(parts)
                    if plan.env_overrides:
                        run_env.update(plan.env_overrides)

                    # Dynamic EGL shim hook ONLY for Mali GPU family (Exynos)
                    gpu_fam = getattr(runtime.profile, "gpu_family", "").lower()
                    if gpu_fam == "mali":
                        shim_path = Path.home() / "libegl_shim.so"
                        if shim_path.is_file() and "libegl_shim.so" not in run_env.get("LD_PRELOAD", ""):
                            cur_preload = run_env.get("LD_PRELOAD", "")
                            run_env["LD_PRELOAD"] = f"{shim_path}:{cur_preload}".rstrip(":")

                except ImportError as imp_err:
                    from termux_stt.exceptions import PlatformNotSupportedError, ErrorCode
                    raise PlatformNotSupportedError(
                        "[ERROR: AMEVA-STT-E001] GPU acceleration requires 'ameva-runtime'.\n"
                        "Cause: Hardware abstraction provider 'ameva-runtime' is not installed.\n"
                        "Action Required: Install the hardware acceleration package via:\n"
                        "  pip install ameva-runtime\n"
                        "Documentation: https://github.com/uno-km/termux-stt",
                        code=ErrorCode.RUNTIME_NOT_INSTALLED,
                    ) from imp_err
            else:
                cmd.extend(["-dev", "-1", "-t", str(self.threads)])
                run_env = os.environ.copy()

            # Passthrough raw extra_args if provided (list or string)
            extra_args = opts.get("extra_args")
            if extra_args:
                if isinstance(extra_args, list):
                    cmd.extend(extra_args)
                elif isinstance(extra_args, str):
                    import shlex
                    cmd.extend(shlex.split(extra_args))

            logger.info("Running whisper.cpp: %s", " ".join(cmd))
            result = run_isolated(cmd, env=run_env)

            if result.returncode != 0:
                raise RuntimeError(
                    f"whisper.cpp exited with code {result.returncode}: "
                    f"{result.stderr}"
                )

            # Strict Zero-Silent-Fallback Verification of Vulkan backend in GPU mode
            if dev_lower in ("gpu", "vulkan"):
                stderr_text = result.stderr or ""
                lower_err = stderr_text.lower()
                fallback_indicators = [
                    "no devices found",
                    "no gpu found",
                    "failed to initialize",
                    "vk_error",
                    "llvmpipe",
                ]
                for indicator in fallback_indicators:
                    if indicator in lower_err:
                        from termux_stt.exceptions import PlatformNotSupportedError, ErrorCode
                        raise PlatformNotSupportedError(
                            f"[ERROR: AMEVA-STT-E002] Vulkan GPU verification failed or fell back to CPU.\n"
                            f"Indicator detected: '{indicator}'\n"
                            f"Hardware stderr log:\n{stderr_text}\n"
                            f"Execution halted strictly without silent CPU fallback under Zero-Silent-Fallback policy.",
                            code=ErrorCode.VULKAN_DEVICE,
                        )
                if not any(k in lower_err for k in ("using vulkan", "vulkan0", "found gpu device", "vulkan devices")):
                    from termux_stt.exceptions import PlatformNotSupportedError, ErrorCode
                    raise PlatformNotSupportedError(
                        f"[ERROR: AMEVA-STT-E002] Explicit GPU backend requested ('{self.device}'), "
                        f"but whisper.cpp did not confirm active Vulkan execution.\n"
                        f"Hardware stderr log:\n{stderr_text}\n"
                        f"Execution halted strictly under Zero-Silent-Fallback policy.",
                        code=ErrorCode.VULKAN_DEVICE,
                    )

            # 4. Parse JSON result (written to <wav>.json)
            json_file = f"{wav_path}.json"
            segments: List[Segment] = []
            full_text = ""

            if os.path.exists(json_file):
                with open(json_file, "r", encoding="utf-8", errors="replace") as fh:
                    segments = self._parse_whisper_json(fh.read())
                full_text = " ".join(s.text for s in segments)
                try:
                    os.remove(json_file)
                except OSError as _tmp_del_err:
                    import logging; logging.getLogger(__name__).debug("temp file cleanup OSError: %s", _tmp_del_err)

            # Fallback: parse stdout directly if JSON was missing or empty
            if not segments and result.stdout:
                import re
                pattern = re.compile(r"\[(\d{2}):(\d{2}):([\d\.]+)\s*-->\s*(\d{2}):(\d{2}):([\d\.]+)\]\s*(.*)")
                for line in result.stdout.splitlines():
                    m = pattern.search(line)
                    if m:
                        h1, m1, s1, h2, m2, s2, txt = m.groups()
                        t0 = int(h1) * 3600 + int(m1) * 60 + float(s1)
                        t1 = int(h2) * 3600 + int(m2) * 60 + float(s2)
                        txt = txt.strip()
                        if txt:
                            segments.append(Segment(start=t0, end=t1, text=txt))
                if segments:
                    full_text = " ".join(s.text for s in segments)
                elif result.stdout.strip():
                    full_text = result.stdout.strip()
                    segments = [Segment(start=0.0, end=0.0, text=full_text)]

            return TranscriptResult(
                text=full_text,
                language=self.lang,
                segments=segments,
            )
        finally:
            json_file = f"{wav_path}.json"
            if os.path.exists(json_file):
                try:
                    os.remove(json_file)
                except OSError as _tmp_del_err:
                    import logging; logging.getLogger(__name__).debug("temp file cleanup OSError: %s", _tmp_del_err)
            if is_temp_wav and os.path.exists(wav_path):
                try:
                    os.remove(wav_path)
                except OSError as _tmp_del_err:
                    import logging; logging.getLogger(__name__).debug("temp file cleanup OSError: %s", _tmp_del_err)

    def stream_mic(
        self, duration: Optional[float] = None
    ) -> Iterator[Segment]:
        """Stream transcription from the device microphone.

        Records audio in chunks via ``termux-microphone-record``, runs
        VAD to detect speech boundaries, and transcribes each utterance
        with whisper.cpp.
        """
        import tempfile

        from termux_stt.audio.mic import MicCapture

        mic = MicCapture()
        chunk_sec = 5.0  # seconds per chunk

        for chunk_bytes in mic.stream(duration=duration, chunk_sec=chunk_sec):
            # Write chunk to a temp WAV for whisper.cpp
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp:
                tmp_path = tmp.name
                # Write a minimal WAV header + PCM data
                self._write_wav(tmp, chunk_bytes, sample_rate=16000)

            try:
                result = self.transcribe(tmp_path)
                for seg in result.segments:
                    yield seg
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError as _tmp_del_err:
                    import logging; logging.getLogger(__name__).debug("temp file cleanup OSError: %s", _tmp_del_err)

    def stream_file(
        self, audio_path: str, chunk_sec: float = 5.0
    ) -> Iterator[Segment]:
        """Stream transcription from a file in chunks."""
        import tempfile
        import wave

        from termux_stt.audio.preprocessor import preprocess

        wav_path = preprocess(audio_path, target_sr=16000, force_mono=True)
        with wave.open(wav_path, "rb") as wf:
            chunk_frames = int(chunk_sec * wf.getframerate())
            offset = 0.0
            while True:
                data = wf.readframes(chunk_frames)
                if len(data) == 0:
                    break

                with tempfile.NamedTemporaryFile(
                    suffix=".wav", delete=False
                ) as tmp:
                    tmp_path = tmp.name
                    self._write_wav(tmp, data, sample_rate=wf.getframerate())

                try:
                    result = self.transcribe(tmp_path)
                    for seg in result.segments:
                        yield Segment(
                            start=offset + seg.start,
                            end=offset + seg.end,
                            text=seg.text,
                            speaker=seg.speaker,
                            confidence=seg.confidence,
                        )
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError as _tmp_del_err:
                        import logging; logging.getLogger(__name__).debug("temp file cleanup OSError: %s", _tmp_del_err)

                actual_frames = len(data) // (wf.getsampwidth() * wf.getnchannels())
                offset += actual_frames / wf.getframerate()

    def diarize(
        self, audio_path: str, num_speakers: int = 2, **kwargs: Any
    ) -> DiarizedResult:
        """Run STT with speaker diarization.

        Delegates to HybridEngine (Vosk X-Vector + Whisper STT) when available,
        or wraps transcript segments into a valid DiarizedResult.
        """
        try:
            from .hybrid_engine import HybridEngine
            hybrid = HybridEngine(self.config)
            return hybrid.diarize(audio_path, num_speakers=num_speakers, **kwargs)
        except Exception as exc:
            logger.debug("Hybrid diarization delegation unavailable (%s), falling back to standalone diarized result", exc)
            res = self.transcribe(audio_path, **kwargs)
            speaker_label = "Speaker_0" if num_speakers <= 1 else "Speaker_Unknown"
            diarized_segments = [
                Segment(
                    start=s.start,
                    end=s.end,
                    text=s.text,
                    speaker=speaker_label,
                    confidence=s.confidence,
                )
                for s in res.segments
            ]
            return DiarizedResult(
                text=res.text,
                language=res.language,
                segments=diarized_segments,
                duration=res.duration,
                speakers=[speaker_label] if diarized_segments else [],
            )

    def get_info(self) -> Dict[str, Any]:
        """Return engine status information."""
        try:
            binary_path = self._get_binary_path()
        except FileNotFoundError:
            binary_path = None

        info = {
            "name": "whisper.cpp",
            "model": self.model,
            "language": self.lang,
            "device": str(getattr(self.config, "device", None) or self.device),
            "threads": self.threads,
            "binary_path": binary_path,
            "quantization": self.config.quantization,
        }
        if self.ctx:
            info["backend_type"] = self.ctx.backend_type
            info["is_gpu"] = self.ctx.is_gpu
            info["device_name"] = self.ctx.device_name
        return info

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_wav(fh, pcm_data: bytes, sample_rate: int = 16000) -> None:
        """Write raw PCM s16le data as a WAV file."""
        import struct

        num_channels = 1
        sample_width = 2  # 16-bit
        data_size = len(pcm_data)
        header_size = 44

        fh.write(b"RIFF")
        fh.write(struct.pack("<I", data_size + header_size - 8))
        fh.write(b"WAVE")
        fh.write(b"fmt ")
        fh.write(struct.pack("<I", 16))  # chunk size
        fh.write(struct.pack("<H", 1))   # PCM format
        fh.write(struct.pack("<H", num_channels))
        fh.write(struct.pack("<I", sample_rate))
        fh.write(struct.pack("<I", sample_rate * num_channels * sample_width))
        fh.write(struct.pack("<H", num_channels * sample_width))
        fh.write(struct.pack("<H", sample_width * 8))
        fh.write(b"data")
        fh.write(struct.pack("<I", data_size))
        fh.write(pcm_data)
