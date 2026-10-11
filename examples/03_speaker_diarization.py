# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
# examples/03_speaker_diarization.py
# 실행 방법: python 03_speaker_diarization.py
# 이 예제는 화자 분리(Diarization)를 수행합니다.

import termux_stt


def main():
    engine = termux_stt.create_engine("whisper")

    print("화자 분리를 시작합니다...")
    result = engine.diarize("sample_audio.wav", num_speakers=2)

    for segment in result.segments:
        print(f"[{segment.speaker}] {segment.text}")

if __name__ == "__main__":
    main()
