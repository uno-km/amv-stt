# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from termux_stt.export.result import TranscriptResult


def _format_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS,mmm"""
    total_millis = max(0, int(round(seconds * 1000)))
    hours = total_millis // 3600000
    total_millis %= 3600000
    minutes = total_millis // 60000
    total_millis %= 60000
    secs = total_millis // 1000
    millis = total_millis % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def to_srt(result: TranscriptResult) -> str:
    """Generate SRT format from TranscriptResult."""
    lines = []
    for i, seg in enumerate(result.segments, 1):
        start = _format_timestamp(seg.start)
        end = _format_timestamp(seg.end)
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        text = seg.text.strip()
        if hasattr(seg, 'speaker') and seg.speaker:
            text = f"[{seg.speaker}] {text}"
        lines.append(text)
        lines.append("")
    return "\n".join(lines)

def save_srt(result: TranscriptResult, output_path: str) -> None:
    """Save TranscriptResult as SRT file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(to_srt(result))
