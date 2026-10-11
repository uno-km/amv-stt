#!/data/data/com.termux/files/usr/bin/bash
# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
set -e

echo "Downloading models..."
# Mock model download
mkdir -p ~/.cache/termux_stt/models
echo "Mock model downloaded" > ~/.cache/termux_stt/models/whisper-tiny.txt
echo "Mock model downloaded" > ~/.cache/termux_stt/models/vosk-small-ko.txt
echo "Mock model downloaded" > ~/.cache/termux_stt/models/silero-vad.txt
echo "Models downloaded."
