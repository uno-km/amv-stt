# v2.1.0 (2026-10-13) — Neural Multi-Speaker Diarization & Concurrent GPU/CPU Pipeline

Replaced legacy Vosk with neural speaker diarization (PyAnnote 3.0 + CAM++ 192d + TS-VAD overlap resolver), introduced concurrent Whisper GPU and Sherpa CPU dual-pipeline for 4x speedup, and standardized on Apache-2.0.

### Key Changes
- Deployed Neural Multi-Speaker Diarization using PyAnnote 3.0 segmentation and 3D-Speaker CAM++ 192d embeddings.
- Implemented TS-VAD multi-label overlap resolver for simultaneous speech separation.
- Engineered Concurrent Dual-Pipeline (Whisper Vulkan GPU || Sherpa Diarizer CPU) achieving 4x diarization speedup.
- Deprecated and removed legacy Vosk statistical engine.
- Standardized package licensing under Apache-2.0 with OpenSSF SPDX headers.

---

# Release Notes - termux-stt v1.3.3

**Release Tag**: `v1.3.3`  
**Distribution Channels**: PyPI (`termux-stt`), NPM (`termux-stt`), GitHub Releases  
**Target Platform**: Android Termux (ARM64 / aarch64 Bionic)  
**License**: Apache-2.0  

---

## Highlights & Key Architectural Changes

### 1. Unified 5-Backend Standardization
- **Ecosystem Whitelist Governance**: Aligned all CLI subcommands (`transcribe`, `stream`, `diarize`) to the standard 5-backend options: `["auto", "gpu", "vulkan", "opencl", "cpu"]`.
- **Fail-Fast Defense**: Rejected unauthorized options like `cpu_neon` with strict parameter diagnostics.

### 2. Zero-Regression Full Test Pass
- **Complete Test Coverage**: Validated 57 passed tests across Whisper hybrid routing, Vosk engine, Sherpa-ONNX, and audio preprocessing without errors.
