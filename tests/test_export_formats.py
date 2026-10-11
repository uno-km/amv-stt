# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from termux_stt.export.result import Segment, TranscriptResult


def test_srt_format():
    res = TranscriptResult(text="Hello", segments=[Segment(0, 1, "Hello")])
    srt = res.to_srt()
    assert "00:00:00,000" in srt

def test_vtt_format():
    res = TranscriptResult(text="Hello", segments=[Segment(0, 1, "Hello")])
    vtt = res.to_vtt()
    assert "WEBVTT" in vtt

def test_rttm_format():
    res = TranscriptResult(text="Hello", segments=[Segment(0, 1, "Hello", speaker="SPEAKER_01")])
    rttm = res.to_rttm()
    assert "SPEAKER_01" in rttm

def test_json_export():
    res = TranscriptResult(text="Hello", segments=[Segment(0, 1, "Hello")])
    j = res.to_json()
    assert "Hello" in j
