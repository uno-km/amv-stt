#!/data/data/com.termux/files/usr/bin/bash
# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
set -e

echo "Installing whisper.cpp dependencies..."
pkg install -y cmake make git clang

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
mkdir -p "$PREFIX/bin" "$PREFIX/lib"

git clone https://github.com/ggml-org/whisper.cpp.git /tmp/whisper.cpp || true
cd /tmp/whisper.cpp

# 1. Provision ameva-runtime
if command -v pip >/dev/null 2>&1; then
    pip install ameva-runtime || true
fi

# 2. Build whisper.cpp
cmake -B build -DWHISPER_NEON=ON -DGGML_VULKAN=ON -DCMAKE_BUILD_TYPE=Release 2>/dev/null || \
cmake -B build -DWHISPER_NEON=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)

find build -name "*.so*" -type f -exec cp -f {} "$PREFIX/lib/" \; 2>/dev/null || true
cp build/bin/main "$PREFIX/bin/whisper-cli" 2>/dev/null || cp build/bin/whisper-cli "$PREFIX/bin/whisper-cli" 2>/dev/null || true
ln -sf "$PREFIX/bin/whisper-cli" "$PREFIX/bin/whisper-cpp"
chmod 0755 "$PREFIX/bin/whisper-cli"
chmod 0755 "$PREFIX/lib/"*.so* 2>/dev/null || true
echo "whisper.cpp installed to $PREFIX/bin"
