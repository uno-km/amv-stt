# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from termux_stt.export.result import DiarizedResult


def to_rttm(result: DiarizedResult, file_id: str = 'audio') -> str:
    """Generate NIST RTTM format from DiarizedResult."""
    lines = []
    for seg in result.segments:
        start = f"{seg.start:.3f}"
        duration = f"{(seg.end - seg.start):.3f}"
        speaker = seg.speaker if seg.speaker else "Unknown"

        # RTTM Format: SPEAKER <file_id> 1 <start> <duration> <NA> <NA> <speaker_label> <NA> <NA>
        lines.append(f"SPEAKER {file_id} 1 {start} {duration} <NA> <NA> {speaker} <NA> <NA>")

    return "\n".join(lines) + "\n"

def save_rttm(result: DiarizedResult, output_path: str, file_id: str = 'audio') -> None:
    """Save DiarizedResult as RTTM file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(to_rttm(result, file_id))
