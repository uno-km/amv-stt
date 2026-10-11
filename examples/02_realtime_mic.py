# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
# examples/02_realtime_mic.py
# 실행 방법: python 02_realtime_mic.py
# 이 예제는 마이크 입력을 실시간으로 스트리밍하여 전사합니다.

import termux_stt


def main():
    engine = termux_stt.create_engine("sherpa-onnx")

    print("마이크 입력을 시작합니다... (종료: Ctrl+C)")
    try:
        for segment in engine.stream_mic(duration=10.0):
            print(f"[{segment.start:.2f}s - {segment.end:.2f}s] {segment.text}")
    except KeyboardInterrupt:
        print("스트리밍을 종료합니다.")

if __name__ == "__main__":
    main()
