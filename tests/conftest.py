# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import tempfile

import pytest


@pytest.fixture
def sample_audio_path():
    return "dummy_audio.mp3"

@pytest.fixture
def sample_wav_path():
    return "dummy_audio.wav"

@pytest.fixture
def tmp_output_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d
