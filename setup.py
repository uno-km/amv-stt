# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from setuptools import find_packages, setup

setup(
    name="termux-stt",
    version="1.5.0",
    description="Android on-device STT framework for Termux - whisper.cpp, vosk, sherpa-onnx unified",
    author="Eunho Kim (@uno-km)",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "cffi>=1.15.0",
        "srt>=3.5.0",
    ],
    extras_require={
        "dev": ["pytest", "ruff", "mypy"]
    },
    entry_points={
        "console_scripts": [
            "termux-stt = termux_stt.cli.main:main",
            "termux-stt-install = termux_stt.platform.installer:main",
        ]
    }
)
