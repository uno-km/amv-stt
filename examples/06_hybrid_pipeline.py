# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
# examples/06_hybrid_pipeline.py
# 실행 방법: python 06_hybrid_pipeline.py
# Whisper + Vosk 하이브리드 파이프라인.

import termux_stt


def main():
    engine = termux_stt.create_engine("hybrid", lang="ko", num_speakers=2)
    print(f"하이브리드 파이프라인 초기화 완료: {engine.get_info()}")

if __name__ == "__main__":
    main()
