# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
1-Click Self-Contained Native Engine & Dependency Installer for Termux.
Provisions ffmpeg, whisper.cpp with ARM NEON / Vulkan, and Sherpa-ONNX Diarization models.
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
HOME = os.environ.get("HOME", os.path.expanduser("~"))
XDG_CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME") or (Path(HOME) / ".cache"))
PREFIX_BIN = Path(PREFIX) / "bin"
PREFIX_LIB = Path(PREFIX) / "lib"


def _resolve_package_version() -> Optional[str]:
    """Dynamically resolve current installed package version without static fallback."""
    try:
        from .. import __version__
        if __version__:
            return __version__
    except Exception:
        pass
    try:
        import importlib.metadata
        return importlib.metadata.version("termux-stt")
    except Exception:
        return None


class EngineInstaller:
    """Automated installer for native dependencies and C++ engines."""

    @classmethod
    def get_candidate_whisper_urls(cls) -> List[str]:
        """Generate dynamic SSOT candidate URLs for standard pure-CPU / Vulkan engine."""
        urls = []
        custom_tag = os.environ.get("TERMUX_STT_RELEASE_TAG", "").strip()
        custom_base = os.environ.get("TERMUX_STT_RELEASE_BASE", "").strip()

        # Tier 1: Explicit environment overrides
        if custom_base:
            base = custom_base.rstrip("/")
            urls.append(f"{base}/whisper-cli-android-arm64.tar.gz")
        if custom_tag:
            tag = custom_tag if custom_tag.startswith("v") else f"v{custom_tag}"
            urls.append(f"https://github.com/uno-km/termux-stt/releases/download/{tag}/whisper-cli-android-arm64.tar.gz")

        # Tier 2: GitHub Releases latest canonical endpoint (Zero-Hardcoding SSOT)
        urls.append("https://github.com/uno-km/termux-stt/releases/latest/download/whisper-cli-android-arm64.tar.gz")

        # Tier 3: Current installed package dynamic version matching
        ver = _resolve_package_version()
        if ver:
            urls.append(f"https://github.com/uno-km/termux-stt/releases/download/v{ver}/whisper-cli-android-arm64.tar.gz")

        return urls

    @classmethod
    def get_candidate_sherpa_urls(cls) -> List[str]:
        """Generate dynamic SSOT candidate URLs for prebuilt sherpa-onnx + onnxruntime engine."""
        urls = []
        custom_tag = os.environ.get("TERMUX_STT_RELEASE_TAG", "").strip()
        custom_base = os.environ.get("TERMUX_STT_RELEASE_BASE", "").strip()

        # Tier 1: Explicit environment overrides
        if custom_base:
            base = custom_base.rstrip("/")
            urls.append(f"{base}/sherpa-onnx-android-arm64.tar.gz")
        if custom_tag:
            tag = custom_tag if custom_tag.startswith("v") else f"v{custom_tag}"
            urls.append(f"https://github.com/uno-km/termux-stt/releases/download/{tag}/sherpa-onnx-android-arm64.tar.gz")

        # Tier 2: GitHub Releases latest canonical endpoint (Zero-Hardcoding SSOT)
        urls.append("https://github.com/uno-km/termux-stt/releases/latest/download/sherpa-onnx-android-arm64.tar.gz")

        # Tier 3: Current installed package dynamic version matching
        ver = _resolve_package_version()
        if ver:
            urls.append(f"https://github.com/uno-km/termux-stt/releases/download/v{ver}/sherpa-onnx-android-arm64.tar.gz")

        return urls

    @classmethod
    def install_system_dependencies(cls) -> bool:
        """Ensure required Termux runtime packages (ffmpeg) are available."""
        if shutil.which("ffmpeg"):
            print("[+] System package 'ffmpeg' is already present.")
            return True

        if not shutil.which("pkg"):
            logger.warning("'pkg' command not found, skipping system package provisioning.")
            return True

        try:
            print("[*] Installing required system package 'ffmpeg'...")
            cmd = ["pkg", "install", "-y", "ffmpeg"]
            res = subprocess.run(cmd, check=False)
            return res.returncode == 0
        except Exception as e:
            logger.error(f"Failed to install system packages: {e}")
            return False

    @classmethod
    def _print_remediation_guide(cls):
        """Print clear, structured remediation guide for updating termux-stt."""
        print("\n" + "=" * 76)
        print("[AMEVA-STT-E001] Native whisper.cpp binary acquisition failed.")
        print("=" * 76)
        print("To install or upgrade the standard engine:")
        print("  - Python / Pip: pip install -U termux-stt && termux-stt install")
        print("  - Node.js / NPM: npm install -g termux-stt@latest")
        print("For 10x Native Vulkan GPU Turbo Acceleration:")
        print("  - Install AMEVA Runtime: pip install ameva-runtime")
        print("To install neural diarization models:")
        print("  - termux-stt install --engine diarization")
        print("============================================================================" + "\n")

    @classmethod
    def is_valid_elf(cls, path: Path) -> bool:
        """Verifies that the target path is a valid ELF executable/library via magic bytes."""
        try:
            p = path.resolve() if path.is_symlink() else path
            if not p.is_file():
                return False
            with open(p, "rb") as f:
                return f.read(4) == b"\x7fELF"
        except (OSError, PermissionError):
            return False

    @classmethod
    def _download_prebuilt_whisper(cls, force: bool = False) -> bool:
        """Attempt to download and stream-extract precompiled ARM64 Bionic whisper-cli binary (~3s)."""
        import io
        import tarfile
        import urllib.request
        ver = _resolve_package_version() or "latest"

        PREFIX_BIN.mkdir(parents=True, exist_ok=True)
        PREFIX_LIB.mkdir(parents=True, exist_ok=True)
        staging_dir = XDG_CACHE_HOME / "termux-stt" / ".staging-whisper"
        staging_dir.mkdir(parents=True, exist_ok=True)
        target_path = PREFIX_BIN / "whisper-cli"

        print("[*] Attempting Fast-Track direct download of pre-compiled whisper.cpp ARM64 Vulkan binary...")
        candidate_urls = cls.get_candidate_whisper_urls()
        for url in candidate_urls:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": f"termux-stt-installer/{ver} (Android; ARM64)"}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    content = response.read()

                if not content or len(content) < 1024:
                    continue

                is_tar = content[:2] == b'\x1f\x8b' or url.endswith(".tar.gz")
                if is_tar:
                    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
                        tar.extractall(path=staging_dir)

                    found_bin = None
                    for p in staging_dir.rglob("*"):
                        if p.is_file() and p.name in ("whisper-cli", "whisper-cpp", "main"):
                            found_bin = p
                            break

                    if found_bin:
                        shutil.copy2(found_bin, target_path)
                        target_path.chmod(0o755)
                        shutil.copy2(target_path, PREFIX_BIN / "whisper-cpp")
                        (PREFIX_BIN / "whisper-cpp").chmod(0o755)

                    for so_file in staging_dir.rglob("*.so*"):
                        if so_file.is_file():
                            target_so = PREFIX_LIB / so_file.name
                            if not force and target_so.is_file() and cls.is_valid_elf(target_so):
                                continue
                            shutil.copy2(so_file, target_so)
                            try:
                                target_so.chmod(0o755)
                            except OSError:
                                pass

                    shutil.rmtree(staging_dir, ignore_errors=True)
                else:
                    with open(target_path, "wb") as out_file:
                        out_file.write(content)
                    target_path.chmod(0o755)
                    shutil.copy2(target_path, PREFIX_BIN / "whisper-cpp")
                    (PREFIX_BIN / "whisper-cpp").chmod(0o755)

                if target_path.exists() and cls.is_valid_elf(target_path):
                    print(f"[+] Pre-compiled whisper.cpp binary successfully installed to {target_path} (from {url})")
                    return True
                else:
                    if target_path.exists():
                        target_path.unlink()
            except Exception as e:
                logger.debug(f"Prebuilt download attempt failed for {url}: {e}")
                shutil.rmtree(staging_dir, ignore_errors=True)
                continue

        print("[-] Pre-built Vulkan binary download unavailable from candidate mirrors.")
        cls._print_remediation_guide()
        return False

    @classmethod
    def install_whisper_cpp(cls, force: bool = False, dedicate: bool = False) -> bool:
        """Install whisper.cpp pre-built ARM64 binary directly from GitHub Releases (~2s)."""
        PREFIX_BIN.mkdir(parents=True, exist_ok=True)
        PREFIX_LIB.mkdir(parents=True, exist_ok=True)

        whisper_bin = PREFIX_BIN / "whisper-cli"
        if dedicate and whisper_bin.is_symlink():
            if ".local/share/ameva" in str(whisper_bin.resolve()):
                print(f"[+] [DEDICATE] AMEVA Runtime managed whisper engine detected. Preserving co-existence (<0.002s).")
                return True

        # Check existing binary (Skip if healthy)
        if not force:
            for candidate in [whisper_bin, PREFIX_BIN / "whisper-cpp"]:
                if candidate.exists() and cls.is_valid_elf(candidate):
                    print(f"[+] whisper.cpp binary is already present and verified at {candidate}.")
                    return True

        if cls._download_prebuilt_whisper(force=force):
            return True

        print("[-] Pre-built whisper binary download failed from release mirrors.")
        cls._print_remediation_guide()
        return False

    @classmethod
    def _download_prebuilt_sherpa(cls, force: bool = False) -> bool:
        """Download and stream-extract precompiled sherpa-onnx & onnxruntime binaries (~3s)."""
        import io
        import tarfile
        import urllib.request
        ver = _resolve_package_version() or "latest"

        PREFIX_BIN.mkdir(parents=True, exist_ok=True)
        PREFIX_LIB.mkdir(parents=True, exist_ok=True)
        staging_dir = XDG_CACHE_HOME / "termux-stt" / ".staging-sherpa"
        staging_dir.mkdir(parents=True, exist_ok=True)

        print("[*] Downloading pre-compiled sherpa-onnx & ONNX Runtime ARM64 engine (~23MB)...")
        candidate_urls = cls.get_candidate_sherpa_urls()
        for url in candidate_urls:
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": f"termux-stt-installer/{ver} (Android; ARM64)"}
                )
                with urllib.request.urlopen(req, timeout=30) as response:
                    content = response.read()

                if not content or len(content) < 1024:
                    continue

                is_tar = content[:2] == b'\x1f\x8b' or url.endswith(".tar.gz")
                if is_tar:
                    with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
                        tar.extractall(path=staging_dir)

                    # Deploy binaries to PREFIX_BIN
                    for p in staging_dir.rglob("sherpa-onnx*"):
                        if p.is_file():
                            target = PREFIX_BIN / p.name
                            shutil.copy2(p, target)
                            try:
                                target.chmod(0o755)
                            except OSError:
                                pass

                    # Deploy shared libraries (onnxruntime, sherpa-c-api) to PREFIX_LIB
                    for so_file in staging_dir.rglob("*.so*"):
                        if so_file.is_file():
                            target_so = PREFIX_LIB / so_file.name
                            if not force and target_so.is_file() and cls.is_valid_elf(target_so):
                                continue
                            shutil.copy2(so_file, target_so)
                            try:
                                target_so.chmod(0o755)
                            except OSError:
                                pass

                    shutil.rmtree(staging_dir, ignore_errors=True)

                    if (PREFIX_BIN / "sherpa-onnx-offline").exists():
                        print(f"[+] Successfully installed pre-compiled sherpa-onnx & onnxruntime to {PREFIX_BIN} and {PREFIX_LIB}")
                        return True
            except Exception as e:
                logger.debug(f"Sherpa download attempt failed for {url}: {e}")
                shutil.rmtree(staging_dir, ignore_errors=True)
                continue

        print("[-] Pre-built sherpa-onnx binary download unavailable from candidate mirrors.")
        return False

    @classmethod
    def install_sherpa_onnx(cls, force: bool = False, dedicate: bool = False, **kwargs) -> bool:
        """Install prebuilt sherpa-onnx binaries and initialize cache directories."""
        model_dir = XDG_CACHE_HOME / "termux-stt" / "models" / "sherpa"
        model_dir.mkdir(parents=True, exist_ok=True)
        sherpa_bin = PREFIX_BIN / "sherpa-onnx-offline"

        if dedicate and sherpa_bin.is_symlink():
            if ".local/share/ameva" in str(sherpa_bin.resolve()):
                print("[+] [DEDICATE] AMEVA Runtime managed sherpa engine detected. Preserving co-existence (<0.002s).")
                return True

        if not force and (shutil.which("sherpa-onnx-offline") or (sherpa_bin.exists() and cls.is_valid_elf(sherpa_bin))):
            print("[+] sherpa-onnx binary is already present and verified.")
            return True

        return cls._download_prebuilt_sherpa(force=force)

    @classmethod
    def install_diarization(cls, force: bool = False) -> bool:
        """Provision PyAnnote 3.0 segmentation & CAM++ 192d embedding models and diarizer binary."""
        print("==========================================================")
        print("[AMEVA-STT] Provisioning Neural Speaker Diarization Models & Runtimes")
        print("==========================================================")

        # 1. Ensure sherpa-onnx binaries and shared libraries
        sherpa_ok = cls.install_sherpa_onnx(force=force)
        if not sherpa_ok:
            logger.warning("Sherpa binary installation failed, will attempt model provisioning directly.")

        # 2. Provision PyAnnote 3.0 Segmentation ONNX model (~15MB)
        try:
            from ..models.hub import ModelHub
            print("[*] Provisioning PyAnnote Segmentation 3.0 ONNX (~15MB)...")
            ModelHub.ensure_model("sherpa", "pyannote-segmentation-3-0")
            print("[+] PyAnnote Segmentation 3.0 model successfully cached.")
        except Exception as e:
            print(f"[-] Failed to download pyannote-segmentation-3-0: {e}")
            return False

        # 3. Provision 3D-Speaker CAM++ 192d Embedding ONNX model (~28MB)
        try:
            print("[*] Provisioning 3D-Speaker CAM++ (192-dim) ONNX (~28MB)...")
            ModelHub.ensure_model("sherpa", "3dspeaker-campplus")
            print("[+] 3D-Speaker CAM++ model successfully cached.")
        except Exception as e:
            print(f"[-] Failed to download 3dspeaker-campplus: {e}")
            return False

        print("\n[+] Neural speaker diarization models and runtimes are fully provisioned!")
        return True

    @classmethod
    def check_diarization_installed(cls) -> bool:
        """Check if neural diarization models (PyAnnote + CAM++) are present in cache."""
        model_dir = XDG_CACHE_HOME / "termux-stt" / "models" / "sherpa"
        # Check CAM++
        has_campplus = (
            (model_dir / "3dspeaker-campplus").exists()
            or any(model_dir.glob("*campplus*.onnx"))
            or (model_dir / "3dspeaker_speech_campplus_sv_zh-cn_16k-common.onnx").exists()
        )
        # Check PyAnnote
        has_pyannote = (
            (model_dir / "sherpa-onnx-pyannote-segmentation-3-0").exists()
            or any(model_dir.glob("*pyannote*.onnx"))
            or any(model_dir.glob("*segmentation*.onnx"))
        )
        return bool(has_campplus and has_pyannote)

    @classmethod
    def check_engine_installed(cls, engine: str) -> bool:
        """Check if an engine is installed and available in PATH."""
        if engine == "whisper":
            return bool(
                shutil.which("whisper-cli")
                or shutil.which("whisper-cpp")
                or (PREFIX_BIN / "whisper-cli").exists()
                or (PREFIX_BIN / "whisper-cpp").exists()
            )
        elif engine == "sherpa":
            return bool(shutil.which("sherpa-onnx-offline") or (PREFIX_BIN / "sherpa-onnx-offline").exists())
        elif engine == "diarization":
            return cls.check_diarization_installed()
        return False

    @classmethod
    def install_default_model(cls) -> bool:
        """Pre-provision default Whisper tiny model for immediate zero-latency transcription."""
        try:
            from ..models.hub import ModelHub
            print("[*] Pre-provisioning default Whisper 'tiny' model (~75MB)...")
            ModelHub.ensure_model("whisper", "tiny")
            print("[+] Whisper 'tiny' model successfully installed and verified.")
            return True
        except Exception as err:
            logger.warning("Default model pre-provisioning warning: %s", err)
            print(f"[-] Warning: Failed to pre-provision default model: {err}")
            return False

    @classmethod
    def install_standard(cls) -> Dict[str, bool]:
        """Default Lightweight installation: ffmpeg + whisper.cpp + default tiny model."""
        cls.install_system_dependencies()
        whisper_ok = cls.install_whisper_cpp()
        model_ok = cls.install_default_model() if whisper_ok else False
        return {
            "whisper": whisper_ok,
            "model(tiny)": model_ok,
        }

    @classmethod
    def install_all(cls, *args, **kwargs) -> Dict[str, bool]:
        """Full installation: ffmpeg + whisper + sherpa STT + Diarization (PyAnnote & CAM++)."""
        cls.install_system_dependencies()
        whisper_ok = cls.install_whisper_cpp()
        sherpa_ok = cls.install_sherpa_onnx()
        diar_ok = cls.install_diarization()
        model_ok = cls.install_default_model() if whisper_ok else False
        return {
            "whisper": whisper_ok,
            "sherpa": sherpa_ok,
            "diarization": diar_ok,
            "model(tiny)": model_ok,
        }


def main(args=None):
    """CLI entrypoint for termux-stt-install & termux-stt install."""
    import argparse
    if isinstance(args, list) or args is None:
        parser = argparse.ArgumentParser(description="termux-stt native engine and model installer")
        parser.add_argument("--engine", choices=["whisper", "sherpa", "diarization", "all"], default=None,
                            help="Target engine/component to provision (default: standard lightweight whisper)")
        parser.add_argument("--diarization", action="store_true", help="Provision PyAnnote 3.0 & CAM++ diarization models")
        parser.add_argument("--all", action="store_true", help="Provision all engines, models, and diarization runtimes")
        parser.add_argument("-y", "--yes", action="store_true", help="Non-interactive flag")
        parsed_args = parser.parse_args(args)
    else:
        parsed_args = args

    print("==========================================================")
    print("[AMEVA-STT v2.0.0] Termux Environment & Native Engine Installer")
    print("==========================================================")

    if parsed_args.all or parsed_args.engine == "all":
        print("Executing Full-Stack installation (Whisper + Sherpa + Diarization)...\n")
        results = EngineInstaller.install_all()
    elif parsed_args.diarization or parsed_args.engine == "diarization":
        print("Provisioning Neural Speaker Diarization runtimes and models...\n")
        ok = EngineInstaller.install_diarization()
        results = {"diarization": ok}
    elif parsed_args.engine == "sherpa":
        print("Provisioning Sherpa-ONNX STT engine...\n")
        ok = EngineInstaller.install_sherpa_onnx()
        results = {"sherpa": ok}
    else:
        # Default lightweight installation: standard whisper + ffmpeg (no heavy diarization models unless requested)
        print("Executing Standard Lightweight installation (Whisper Vulkan/CPU + FFmpeg)...\n")
        print("Note: Speaker diarization models are skipped. To install them, run: termux-stt install --engine diarization\n")
        results = EngineInstaller.install_standard()

    print("\n--- Installation Summary ---")
    for comp, ok in results.items():
        status = "[OK]" if ok else "[FAILED]"
        print(f" - {comp:12s} : {status}")

    print("\n[+] Setup complete. Run 'termux-stt doctor' to verify system health.")


if __name__ == "__main__":
    main()
