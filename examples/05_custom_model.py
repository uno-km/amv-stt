# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
# examples/05_custom_model.py
# 실행 방법: python 05_custom_model.py
# 커스텀 모델 경로를 사용하는 예제입니다.

import termux_stt


def main():
    engine = termux_stt.create_engine("vosk", custom_model_path="/path/to/custom/model")
    print(f"커스텀 모델이 준비되었습니다: {engine.get_info()}")

if __name__ == "__main__":
    main()
