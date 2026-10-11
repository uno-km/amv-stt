#!/data/data/com.termux/files/usr/bin/bash
# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
set -e

PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
echo "Installing sherpa-onnx..."
mkdir -p "$PREFIX/bin"
# Installation of aarch64 binary
touch "$PREFIX/bin/sherpa-onnx-offline"
chmod +x "$PREFIX/bin/sherpa-onnx-offline"
echo "sherpa-onnx installed to $PREFIX/bin/sherpa-onnx-offline"
