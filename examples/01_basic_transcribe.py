# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
# examples/01_basic_transcribe.py
# 실행 방법: python 01_basic_transcribe.py
# 이 예제는 Whisper 엔진을 사용하여 오디오 파일을 전사합니다.

import termux_stt


def main():
    # 엔진 생성
    engine = termux_stt.create_engine("whisper", model="base")

    # 전사 수행
    result = engine.transcribe("sample_audio.wav")

    # 결과 출력
    print(f"전사 결과: {result.text}")
    print(f"세그먼트: {result.segments}")

if __name__ == "__main__":
    main()
