# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
# examples/04_batch_processing.py
# 실행 방법: python 04_batch_processing.py
# 디렉토리 내 여러 파일을 배치로 처리합니다.

import os

import termux_stt


def main():
    engine = termux_stt.create_engine("whisper")

    audio_files = ["audio1.wav", "audio2.wav"]

    for file in audio_files:
        if os.path.exists(file):
            print(f"{file} 전사 중...")
            res = engine.transcribe(file)
            print(res.text)

if __name__ == "__main__":
    main()
