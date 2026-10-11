# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import pytest
from termux_stt.platform.installer import EngineInstaller


def test_candidate_whisper_urls_ssot():
    urls = EngineInstaller.get_candidate_whisper_urls()
    assert len(urls) > 0

    # Ensure all urls strictly target whisper-cli-android-arm64.tar.gz for pure CPU free tier
    for url in urls:
        assert url.endswith("whisper-cli-android-arm64.tar.gz"), f"URL does not end with SSOT filename: {url}"
        assert "v1.1.3" not in url, f"Legacy CPU fallback v1.1.3 detected in URLs: {url}"


def test_remediation_guide_output(capsys):
    EngineInstaller._print_remediation_guide()
    captured = capsys.readouterr().out
    assert "[AMEVA-STT-E001]" in captured
    assert "pip install -U termux-stt" in captured
    assert "npm install -g termux-stt@latest" in captured
    assert "pip install ameva-runtime" in captured
