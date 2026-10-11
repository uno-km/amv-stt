# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
AMEVA Unified Hardware & Environment Diagnostics for Termux AI Engines.
Component: [STT]
"""
from __future__ import annotations

import os
import sys
import multiprocessing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Any, List, Dict


@dataclass
class HardwareProfile:
    """Standardized Hardware & Capabilities Profile for Mobile Termux Environment."""
    is_termux: bool = False
    is_android: bool = False
    is_arm64: bool = False
    cpu_count: int = 4
    recommended_threads: int = 4
    ram_total_mb: float = 0.0
    ram_available_mb: float = 0.0
    has_neon: bool = False
    has_fp16: bool = False
    has_dotprod: bool = False
    has_vulkan: bool = False
    gpu_name: Optional[str] = None
    soc_model: Optional[str] = None
    features: List[str] = field(default_factory=list)

    @property
    def soc_name(self) -> str:
        return self.soc_model or "Unknown SoC"

    @property
    def cpu_cores(self) -> int:
        return self.cpu_count

    @property
    def threads(self) -> int:
        return self.recommended_threads

    @property
    def big_cores(self) -> int:
        return self.recommended_threads

    @property
    def little_cores(self) -> int:
        return max(0, self.cpu_count - self.recommended_threads)

    @property
    def neon_support(self) -> bool:
        return self.has_neon

    @property
    def fp16_support(self) -> bool:
        return self.has_fp16



# Backward compatible dataclass alias
@dataclass
class HardwareInfo:
    cpu_model: str = "Unknown ARM"
    cpu_cores: int = 4
    big_cores: int = 4
    little_cores: int = 0
    neon_support: bool = True
    fp16_support: bool = False
    ram_total_mb: int = 0
    ram_available_mb: int = 0
    soc_name: str = "Unknown SoC"
    is_termux: bool = False
    is_android: bool = False

    @property
    def threads(self) -> int:
        return self.big_cores


def is_termux() -> bool:
    if os.environ.get("TERMUX_VERSION") or os.environ.get("TERMUX_APP_PID"):
        return True
    prefix = os.environ.get("PREFIX", "")
    if "com.termux" in prefix:
        return True
    return Path("/data/data/com.termux").is_dir()


def is_android() -> bool:
    """Check whether running on Android (Termux execution implies Android runtime)."""
    return is_termux()



def get_ram_info() -> Tuple[int, int]:
    total, available = 0, 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) // 1024
                elif line.startswith("MemAvailable:"):
                    available = int(line.split()[1]) // 1024
    except Exception:
        pass
    return total, available


def check_neon_support() -> bool:
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read().lower()
            return "neon" in content or "asimd" in content
    except Exception:
        return True if "arm" in sys.platform or "aarch64" in sys.platform else False


def check_fp16_support() -> bool:
    try:
        with open("/proc/cpuinfo", "r") as f:
            content = f.read().lower()
            return "fphp" in content or "asimdhp" in content
    except Exception:
        return False


def get_optimal_threads() -> int:
    cores = multiprocessing.cpu_count()
    return max(1, cores // 2) if cores > 2 else cores


def detect_hardware() -> HardwareProfile:
    cores = multiprocessing.cpu_count()
    big_cores = get_optimal_threads()
    total_ram, avail_ram = get_ram_info()
    return HardwareProfile(
        cpu_count=cores,
        recommended_threads=big_cores,
        ram_total_mb=float(total_ram),
        ram_available_mb=float(avail_ram),
        has_neon=check_neon_support(),
        has_fp16=check_fp16_support(),
        is_termux=is_termux(),
        is_android=is_android(),
    )


GPU_RUNTIME_MIN_VERSION = "2.0.0"


def _require_gpu_runtime(requested_device: str) -> None:
    """Stop with the shared AMU_ERR_RUNTIME_REQUIRED explanation unless ameva-runtime is usable.

    Every explicit GPU request goes through here. There is no CPU fallback: the caller gets
    RuntimeRequiredError and the CLI exits with status 69.
    """
    from termux_stt.exceptions import RuntimeRequiredError
    try:
        from ameva_device import AmevaRuntimeRequiredError, require_ameva_runtime
    except ImportError as exc:
        raise RuntimeRequiredError(
            "[AMU_ERR_RUNTIME_REQUIRED] termux-stt: GPU execution (device='%s') needs ameva-runtime (AMUDA), "
            "and the shared check library 'ameva-device-sdk' is missing from this installation.\n"
            "Nothing was run, and no CPU fallback was used.\n"
            "Install:\n"
            "  pip install \"ameva-runtime>=%s\"\n"
            "  npm install -g @ameva/runtime\n"
            "  Releases and documentation: https://github.com/uno-km/ameva-runtime-releases\n"
            "To run on the CPU instead, use --device cpu.\n" % (requested_device, GPU_RUNTIME_MIN_VERSION)
        ) from exc
    try:
        require_ameva_runtime(
            "termux-stt", "GPU execution (device='%s')" % requested_device,
            min_version=GPU_RUNTIME_MIN_VERSION,
        )
    except AmevaRuntimeRequiredError as exc:
        raise RuntimeRequiredError(str(exc)) from exc


def _note_cpu_instead(reason: str) -> None:
    """auto mode: say on stderr that the GPU was not used, so the CPU run is never silent."""
    import sys
    sys.stderr.write("[termux-stt] GPU not used: %s. This run uses the CPU. "
                     "To enable the GPU: pip install ameva-runtime (https://github.com/uno-km/ameva-runtime-releases)\n" % reason)
    sys.stderr.flush()


def resolve_device(requested_device: str = "auto") -> Tuple[str, int]:
    from termux_stt.exceptions import PlatformNotSupportedError, ErrorCode

    req = str(requested_device or "auto").strip().lower()
    optimal_threads = get_optimal_threads()

    if req == "cpu":
        return "cpu", optimal_threads

    if req in ("vulkan", "gpu"):
        # Every explicit GPU request needs ameva-runtime (AMUDA); no CPU fallback.
        _require_gpu_runtime(req)
        from ameva_runtime import vulkan as avr

        try:
            if hasattr(avr, "get_or_create_context"):
                ctx = avr.get_or_create_context("vulkan")
            elif hasattr(avr, "create_context"):
                ctx = avr.create_context("vulkan")
            else:
                ctx = avr.VulkanContext("vulkan")

            is_vk = ctx.backend_type == "vulkan" or getattr(ctx, "is_gpu", False)
            if is_vk:
                return "vulkan", 32
        except Exception as ctx_err:
            raise PlatformNotSupportedError(
                f"[ERROR: AMEVA-STT-E002] Vulkan GPU acceleration was explicitly requested (device='{requested_device}'), "
                f"but Vulkan initialization failed: {ctx_err}.\n"
                "Execution halted strictly without silent fallback to prevent unexpected CPU execution.",
                code=ErrorCode.VULKAN_DEVICE,
            ) from ctx_err

        raise PlatformNotSupportedError(
            f"[ERROR: AMEVA-STT-E002] Vulkan GPU acceleration was explicitly requested (device='{requested_device}'), "
            "but no accessible Vulkan physical device was found on this system.\n"
            "Execution halted strictly without silent fallback to prevent unexpected CPU execution.",
            code=ErrorCode.VULKAN_DEVICE,
        )

    if req == "auto":
        try:
            from ameva_runtime import vulkan as avr
            if hasattr(avr, "get_or_create_context"):
                ctx = avr.get_or_create_context("auto")
            elif hasattr(avr, "create_context"):
                ctx = avr.create_context("auto")
            else:
                ctx = avr.VulkanContext("auto")
            if ctx.backend_type == "vulkan" or getattr(ctx, "is_gpu", False):
                return "vulkan", 32
        except ImportError:
            _note_cpu_instead("ameva-runtime (AMUDA) is not installed")
            return "cpu", optimal_threads
        except Exception as auto_err:
            _note_cpu_instead("GPU initialisation failed (%s)" % auto_err)
            return "cpu", optimal_threads
        _note_cpu_instead("ameva-runtime reported no GPU backend")
        return "cpu", optimal_threads

    raise ValueError(f"Unsupported device '{requested_device}'. Must be one of ['auto', 'gpu', 'vulkan', 'cpu'].")


resolve_device_backend = resolve_device


def bind_hardware(engine: Any, requested_device: str = "auto", **kwargs) -> Optional[Any]:
    device, threads = resolve_device(requested_device)
    if hasattr(engine, "device"):
        setattr(engine, "device", device)
    if hasattr(engine, "threads"):
        setattr(engine, "threads", threads)
    return engine


def get_unified_model_search_dirs(submodule: str = "stt") -> List[Path]:
    dirs: List[Path] = []
    custom = os.environ.get("TERMUX_STT_MODELS_DIR") or os.environ.get("AMEVA_MODELS_DIR")
    if custom:
        dirs.append(Path(custom))
    dirs.append(Path.home() / ".cache" / "termux-stt" / "models")
    dirs.append(Path.home() / ".cache" / "termux-stt")
    dirs.append(Path.home() / ".termux-stt" / "models")
    prefix = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
    dirs.append(Path(prefix) / "share" / "termux-stt" / "models")
    return [d for d in dirs if d.exists()]
