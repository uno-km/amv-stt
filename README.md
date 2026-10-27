# AMV-STT

> **마이그레이션 안내**: 이 패키지는 `termux-stt`에서 `amv-stt`로 이름이 바뀌었습니다. 기존 `termux-stt` 배포본(PyPI/npm)은 호환을 위해 당분간 유지되나 deprecated 상태이며 더 이상 갱신되지 않습니다. `pip install amv-stt` / `npm install amv-stt`로 전환하십시오.
>
> Android **Termux 환경** 또는 **안드로이드 Linux 커널(루팅 없이 Linux 환경이 구동되는 모든 디바이스)** 에서 동작합니다 — Termux 전용이 아닙니다.

[![PyPI](https://img.shields.io/pypi/v/amv-stt.svg?style=flat-square&color=0369a1)](https://pypi.org/project/amv-stt/)
[![Python](https://img.shields.io/pypi/pyversions/amv-stt.svg?style=flat-square)](https://pypi.org/project/amv-stt/)
[![npm](https://img.shields.io/npm/v/amv-stt.svg?style=flat-square&color=b91c1c)](https://www.npmjs.com/package/amv-stt)
[![npm downloads](https://img.shields.io/npm/dm/amv-stt.svg?style=flat-square&color=b91c1c)](https://www.npmjs.com/package/amv-stt)
[![License](https://img.shields.io/badge/License-Apache_2.0-004499.svg?style=flat-square)](https://github.com/uno-km/amv-stt)

> **디바이스 리소스를 활용한 통합 온디바이스 음성인식(STT) 및 차세대 신경망 화자 분리(PyAnnote 3.0 + CAM++ 192d + TS-VAD) 프레임워크**  
> *Unified On-Device Speech-to-Text & Neural Multi-Speaker Diarization (PyAnnote 3.0 + CAM++ 192d + TS-VAD Overlap Resolver)*

---

## Architecture & Overview

Whisper.cpp(네이티브 Vulkan GPU / NEON CPU) 및 Sherpa-ONNX 듀얼 모던 엔진을 통합하고, PyAnnote 3.0 신경망 세그멘테이션, 3D-Speaker CAM++ 192차원 성문 임베딩, TS-VAD 동시 발화(마이크 물림) 분리기를 결합하여 완전 온디바이스 실시간 다중 화자 음성인식을 구현합니다.

Integrates Whisper.cpp (Native Vulkan GPU / NEON CPU) and Sherpa-ONNX with PyAnnote 3.0 neural segmentation, 3D-Speaker CAM++ 192-dim embeddings, and TS-VAD overlapped speech resolution with zero cloud egress.

---

## Installation & Quickstart

### Python (PyPI)
```bash
pip install amv-stt
```
```python
from termux_stt import create_engine

# 1. Initialize Whisper Engine with Vulkan GPU / CPU Hybrid Acceleration
engine = create_engine("whisper", model="small", lang="ko", threads=4, split_mode=True)

# 2. Transcribe Audio directly into Subtitles
result = engine.transcribe("samples/jfk_1min.wav")
print("Transcript:
", result.text)
print("SRT Subtitles:
", result.to_srt())

# 3. Multi-Speaker Neural Diarization (PyAnnote 3.0 + CAM++ 192d + TS-VAD)
hybrid = create_engine("hybrid", lang="ko", num_speakers=2)
diar_result = hybrid.diarize("samples/kor_diarization.wav")
for seg in diar_result.segments:
    print(f"[{seg.speaker}] ({seg.start:.1f}s -> {seg.end:.1f}s): {seg.text}")

```

### Node.js / TypeScript (npm)
```bash
npm install amv-stt
```
```typescript
const { createEngine } = require("amv-stt");

async function main() {
  // 1. Initialize Whisper Engine
  const engine = createEngine("whisper", { model: "tiny", lang: "ko", threads: 4 });

  // 2. Transcribe Audio
  const result = await engine.transcribe("samples/jfk_1min.wav");
  console.log("Transcript:", result.text);
  console.log("SRT Subtitles:
", result.toSrt());

  // 3. Neural Diarization via Hybrid Engine
  const hybrid = createEngine("hybrid", { lang: "ko", numSpeakers: 2 });
  const diarResult = await hybrid.diarize("samples/kor_diarization.wav");
  for (const seg of diarResult.segments) {
    console.log(`[${seg.speaker}] (${seg.start.toFixed(1)}s -> ${seg.end.toFixed(1)}s): ${seg.text}`);
  }
}
main();

```

---

## Official Documentation & Benchmarks
- [Official Architecture & API Reference](https://uno-km.vercel.app/lib/stt/)
- [Ecosystem Metrics & Registry Stats](https://uno-km.vercel.app/foundation/metrics)
- [AMEVA Open-Source Foundation Portal](https://uno-km.vercel.app/foundation/index.html)

---

## License
Licensed under the Apache-2.0 License. Copyright (c) 2026 Eunho Kim ([@uno-km](https://github.com/uno-km)).
