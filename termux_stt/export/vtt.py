# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from termux_stt.export.result import TranscriptResult


def _format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

def to_vtt(result: TranscriptResult) -> str:
    """Generate WebVTT format from TranscriptResult."""
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(result.segments, 1):
        start = _format_timestamp(seg.start)
        end = _format_timestamp(seg.end)
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        text = seg.text.strip()
        if hasattr(seg, 'speaker') and seg.speaker:
            text = f"<v {seg.speaker}>{text}</v>"
        lines.append(text)
        lines.append("")
    return "\n".join(lines)

def save_vtt(result: TranscriptResult, output_path: str) -> None:
    """Save TranscriptResult as VTT file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(to_vtt(result))
