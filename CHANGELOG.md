# v2.1.0 (2026-10-13) — Neural Multi-Speaker Diarization & Concurrent GPU/CPU Pipeline

Replaced legacy Vosk with neural speaker diarization (PyAnnote 3.0 + CAM++ 192d + TS-VAD overlap resolver), introduced concurrent Whisper GPU and Sherpa CPU dual-pipeline for 4x speedup, and standardized on Apache-2.0.

### Key Changes
- Deployed Neural Multi-Speaker Diarization using PyAnnote 3.0 segmentation and 3D-Speaker CAM++ 192d embeddings.
- Implemented TS-VAD multi-label overlap resolver for simultaneous speech separation.
- Engineered Concurrent Dual-Pipeline (Whisper Vulkan GPU || Sherpa Diarizer CPU) achieving 4x diarization speedup.
- Deprecated and removed legacy Vosk statistical engine.
- Standardized package licensing under Apache-2.0 with OpenSSF SPDX headers.

---

# Changelog

All notable changes to termux-stt will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.2] - 2026-09-29

### Fixed & Hardened
- **SmartRouter `-sm` Dynamic Filter**: Automatically suppresses `-sm` (split mode) when the native binary does not declare split mode support in its help manual, preventing unknown option aborts.
- **Thread Flag `-t` De-Duplication**: Enforces single authoritative `-t` argument passed to `whisper-cli`, eliminating duplicate CLI argument collisions.
- **Conditional Vulkan Request Logic**: Constrains `requested_backend="vulkan"` strictly to explicit GPU/Vulkan execution requests, ensuring clean pure-CPU execution when `--device cpu` is selected.
- **Upstream HF Model Registry Alignment**: Synchronized SHA-256 checksums and model endpoints for Whisper quantized GGML models in `registry.py`.

## [1.3.1] - 2026-09-29

### Added & Architectural Breakthrough
- **Asymmetric Hardware Hybrid Pipeline (Encoder Vulkan GPU / Decoder CPU SIMD)**:
  - First-of-its-kind mobile STT optimization offloading compute-bound dense matrix GEMM (Audio Encoder) to Vulkan mobile GPUs while retaining single-token sequential autoregressive inference (Text Decoder) on CPU ARM NEON SIMD.
  - Zero-drift intermediate cross-attention KV caching (`wstate.kv_cross_cpu`) via zero-copy DMA transfer across isolated GGML execution schedulers.
  - Slashes transcription wall-clock latency by up to **21.0%** over pure GPU and **16.5%** over pure CPU on Whisper Small (Galaxy S25: 12.93s vs GPU 16.36s / CPU 15.48s; Galaxy S21: verified stable).
  - Eliminates host CPU thermal saturation on Whisper Large-v3-Turbo by shifting ~80s of intensive encoder compute entirely to Vulkan GPU (saving 28.5s over pure CPU).
- **Dynamic CLI Hybrid Routing Controls**:
  - Added `--split-mode` (`-sm`, `--hybrid`, `--optimize-gpu-cpu`) to orchestrate Vulkan-to-CPU split execution.
  - Added `--optimize-1` to enforce 1 low-power background CPU decoding thread for maximum thermal and power efficiency.
  - Fail-Fast enforcement: actively checks for functional GPU devices and aborts immediately if split mode is requested without hardware acceleration.
- **Universal Multi-SoC Binary Validation**:
  - Shipped unified `whisper-cli-android-arm64-v1.3.0.tar.gz` with cross-platform Vulkan/NEON support across Qualcomm Snapdragon 8 Elite (Adreno 830), Samsung Exynos 2100 (Mali-G78), Exynos 990 (Mali-G77), Exynos 1380 (Mali-G68), and Exynos 1280.
- **Upstream Contribution**:
  - Official upstream PR submitted to `ggml-org/whisper.cpp` ([PR #4089](https://github.com/ggml-org/whisper.cpp/pull/4089)).

## [1.2.15] - 2026-09-28

### Added & Hardened
- **Bionic Linker Zero-Collision Rule**:
  - Dynamically sanitizes Termux `$PREFIX/lib` from `LD_LIBRARY_PATH` during `whisper-cli` execution, preventing Android 15 (Galaxy S25) `libunwindstack.so` (`Xzs_Construct`) symbol collision crashes.
- **Dual-Flagship Native Vulkan Acceleration**:
  - Validated 100% native Vulkan GPU offload across Qualcomm Adreno 830 (Galaxy S25) and ARM Mali-G78 (Galaxy S21) using a unified universal binary bundle (`whisper-cli-android-arm64.tar.gz`).
  - Purged Adreno SPIR-V `[[unroll]]` register pressure linker failures and stabilized Mali BDA (Buffer Device Address) dynamic handling.

## [1.2.13] - 2026-09-28

### Fixed & Hardened
- **Vosk Engine Dependency Auto-Provisioning**:
  - Automatically verifies and installs essential Python runtime bindings (`cffi>=1.15.0`, `srt>=3.5.0`) required for Vosk STT engine execution on Android Termux.
- **Manifest Synchronization & Zero-Drift**:
  - Synchronized package manifests across `pyproject.toml`, `setup.py`, `package.json`, and `termux_stt/__init__.py` to `1.2.13`.
  - Added explicit runtime dependencies `cffi` and `srt` to package declarations.

## [1.2.12] - 2026-09-18

### Changed & Hardened
- **Zero-Hardcoding Dynamic Latest-First Provisioning Architecture**:
  - Permanently purged hardcoded fallback version strings (`1.2.7`) from `termux_stt/platform/installer.py`.
  - Implemented 3-Tier dynamic resolution for all native engines (Whisper.cpp, Sherpa-ONNX, Vosk).
  - Updated `MODEL_REGISTRY['whisper']['tiny']` to point to invariant GitHub Releases latest download endpoint (`ggml-tiny.bin`).
  - Swapped static user agent strings for dynamic package introspection.

## [1.2.11] - 2026-09-18

### Changed & Synchronized
- **Mainline Production Release Synchronization**:
  - Re-aligned release branch directly from `main` with unified binary packaging SSOT.
  - Synchronized default model download mirrors to `v1.2.9` release tag.
  - Upgraded Python wheel, sdist, and NPM package specifications to `1.2.9`.

## [1.2.8] - 2026-09-17

### Added
- **Default Whisper 'Tiny' Model Auto-Provisioning**:
  - `termux-stt install` now automatically provisions the default Whisper `tiny` neural model (`ggml-tiny.bin`, ~75MB) directly into `~/.cache/termux-stt/models/whisper/`, enabling immediate transcription without runtime download lag.
- **Dedicated Releases Asset Hub**:
  - Established standardized `releases/` offline asset package containing prebuilt Bionic C++ engines and model weights with cryptographically verified SHA-256 signatures.

### Fixed & Streamlined
- **Zero-Compilation 1-Click Installer Optimization**:
  - Eliminated mobile on-device cmake/make/clang source compilation fallback and unnecessary apt packaging latency in `installer.py`.
  - Removed internal subprocess pip compilation triggers (`pip install srt`), ensuring 100% pre-built ARM64 binary provisioning across all 3 engines (Whisper, Sherpa-ONNX, Vosk).
- **HuggingFace Upstream Checksum Realignment & Release Model Mirror**:
  - Re-aligned SHA-256 integrity checksums for `tiny` (`be07e048...`) and `small` (`1be3a9b2...`) models to match latest upstream weights.
  - Integrated `ggml-tiny.bin` directly into GitHub Releases `v1.2.8` as primary SSOT mirror with graceful upstream fallback in `hub.py` and `registry.py`.
- **Pure Zero-Dependency Distribution & 120% Pip/NPM Parity**:
  - Streamlined package dependencies to prevent pip resolution deadlocks on clean target environments.
  - Fully synchronized Python (`pyproject.toml`, `setup.py`) and Node.js (`package.json`) to `v1.2.8` with transparent cross-language CLI dispatching.

## [1.2.7] - 2026-09-15

### Added & Optimized
- **Mobile Production Greedy Search Default (`--beam-size 1` / `-bs 1`)**:
  - Standardized `--beam-size` (`-bs`) to 1 across CLI, Python API, and subprocess execution, reducing autoregressive decoder memory bus traffic by 5x and shrinking KV cache footprint from 249MB to 49.8MB without measurable WER loss.
  - Preserved multi-beam exploration (`-bs 5` or higher) as an explicit user parameter.
- **Robust Android UTF-8 Character Replacement Decoding**:
  - Replaced strict UTF-8 decoding with `errors="replace"` across all JSON and stdout/stderr ingestion layers (`whisper_engine.py`, `process_pool.py`), eliminating crashes on non-breaking spaces (`\xa0`) and malformed multibyte sequences.
- **Comprehensive 6-SoC Physical Fleet Benchmark Verification**:
  - Empirically validated across 6 flagship and mid-range mobile SoCs (Snapdragon 8 Elite, Snapdragon 8 Gen 1, Exynos 2100, Exynos 1380, Exynos 1280, Snapdragon 865) on 60.00s audio.
  - Achieved up to 7.56x speedup over multi-threaded ARM NEON CPU compute.
  - Verified Exynos 1280 (Galaxy A53) full Turbo execution (759.52s) via OS zRAM (+2GB RAM Plus) provisioning.
- **Master Technical Treatise Publication**:
  - Published comprehensive research paper *On-Device Vulkan-Accelerated Speech-to-Text on Edge Silicon: A Unified Architectural Treatise, Driver Boundary Analysis, and 6-SoC Empirical Benchmark* (`AOSF-TR-2026-STT01`) in both English and Korean (`docs/research/`).
- **Zero Artificial Restriction Policy**:
  - Enforced OpenSSF open-source compliance by ensuring zero software-level hardware blocks on older chipsets (Galaxy S20 / Snapdragon 865), maintaining user sovereignty and kernel Fail-Fast transparency.

## [1.2.5] - 2026-09-14

### Added & Fixed
- **Qualcomm Adreno Vulkan Native Acceleration & SoftMax wg64 Alignment**:
  - Resolved physical device lost and driver deadlock issues on Qualcomm Adreno GPUs (e.g. Snapdragon 8 Gen 1 / Adreno 730) by strictly constraining Vulkan SoftMax workgroups to hardware subgroup size (64).
  - Implemented automatic hardware-aware routing in Whisper core: automatically bypasses Flash Attention compiler assertion failures in Qualcomm proprietary drivers without requiring manual `--no-flash-attn` (`-nfa`) CLI flags.
  - **Empirical Ground-Truth Speedup**: Galaxy S22 (Adreno 730) achieves **3.73x speedup in neural encoder time (19.14s CPU -> 5.13s GPU)** with zero silent fallback (`fallbacks = 0 p / 0 h`) and ~14% CPU load.
- **Mali-G78 Flash Attention Compatibility Preserved**:
  - Non-Qualcomm GPUs (e.g. ARM Mali-G78 on Galaxy S21) continue to utilize native Vulkan Flash Attention (~17.5s total inference time, zero fallbacks).
- **Zero-Silent-Fallback & Single Bundle SSOT**:
  - Native asset installer provisions verified `whisper-cli-vulkan-android-arm64.tar.gz` with full Bionic RPATH bindings (`$ORIGIN/../lib:$ORIGIN`).
  - Added `-ng` flag support when CPU execution is explicitly requested (`-d cpu`).

---

## [1.2.4] - 2026-09-07

### Added
- **Fast-Track Prebuilt Stream Extractor (~3s)**: Automated stream downloading and in-memory extraction of `whisper-cli-android-arm64.tar.gz` directly from GitHub Releases, avoiding 20-minute on-device C++ compilation.
- **Zero-Hardcoding SSOT Dynamic Candidates**: Replaced legacy static release URLs with dynamic candidate resolution (`TERMUX_STT_RELEASE_TAG`, `v{__version__}`, `releases/latest/download`, and `uno-km/ameva-runtime` SSOT fallback).
- **Vulkan Logic Normalization**: Fixed priority routing to treat precompiled Vulkan+NEON binaries as Priority 1 across all devices, with local CMake/Clang builds reserved strictly as offline fallbacks.
- **Bundled Package Binary Fallback**: Auto-detects and provisions bundled `termux_stt/bin/whisper-cli` if present.

---

## [1.2.3] - 2026-09-07

### Added
- Expanded Section 1 installation documentation with in-depth bundled ARM64 binary architecture details.
- Detailed 3-stage post-installation provisioner (`termux-stt install`) pipeline explanation (native system codecs, adaptive Vulkan GPU clang compilation, sub-engine ecosystem).
- Comprehensive Pure Install vs. Post-Install comparison matrix covering binary states, audio codec support, and execution speed.

---

## [1.2.2] - 2026-09-07

### Added
- Complete 12-tier enterprise English documentation overhaul for PyPI and GitHub/NPM.
- Detailed empirical mobile hardware benchmarks (Snapdragon 8 Elite / Adreno 830, Snapdragon 865, Exynos 1380 / Mali-G68 MP5).
- Full GPU interconnect architecture documentation with SPIR-V compute shader details.
- Comprehensive CPU vs. GPU thermal dissipation, latency, and power efficiency analysis.
- 3-stage 24/7 unattended background execution guide (Termux wake-lock, battery optimization, ADB phantom process killer).
- Expanded technical SEO metadata keywords (50 keywords connecting to AMEVA ecosystem).
- Packaged standalone ARM64 whisper-cli binary asset for GitHub Releases.
- Archived comprehensive engineering guides and legacy reports to ameva-foundation.

### Fixed
- Sanitized author email metadata to official foundation address.
- Removed redundant legacy `npm/` directory in favor of root single source of truth.

---

## [1.2.1] - 2026-09-07

### Fixed
- Fixed npm package.json bin path specification (removed './' prefix).
- Integrated GitHub Actions automated CI/CD release workflow.

---

## [1.2.0] - 2026-09-07

### Added
- Direct integration with `SttAdapter.get_execution_environment()` from `ameva_runtime.adapters` SSOT.
- Eliminated raw `LD_LIBRARY_PATH` pollution and enforced strict Fail-Fast on explicit Vulkan requests.
- Full English localization of diagnostic logs and error reporting.

---

## [1.1.7] - 2026-09-05

### Changed
- Resolved Node.js whisper module require bindings to `@ameva/runtime` preventing MODULE_NOT_FOUND.
- Modernized Whisper.cpp installation toolchain and hardware adapter docstrings.

---

## [1.1.6] - 2026-09-05

### Changed
- Migrated hardware acceleration dependency to unified `ameva-runtime>=2.0.0` and `@ameva/runtime>=2.0.0`.
- Pinned Whisper.cpp Vulkan backend integration with ARM Mali and Qualcomm Adreno silicon-aware routing.

---

## [1.1.4] - 2026-09-02

### Added
- **Hybrid Speech Engine**: Unified runtime across Whisper.cpp, Vosk, and Sherpa-ONNX.
- **Mobile Guard**: Memory budget validation and thermal throttling guard.

### Fixed
- **Benchmark RTF Calculation**: Removed hardcoded 10.0s fallback and added honest N/A handling when audio metadata is unreadable.
- **Engine Load Exception Propagation**: Stored and propagated import errors to callers.

### Verification
- **Unit Tests**: 43 / 43 passed with 100% assertion coverage.
