# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import json
from dataclasses import asdict

from termux_stt.export.result import TranscriptResult


def to_json(result: TranscriptResult, indent: int = 2, ensure_ascii: bool = False) -> str:
    """Generate JSON format from TranscriptResult."""
    data = {
        "text": result.text,
        "language": result.language,
        "segments": [asdict(seg) for seg in result.segments]
    }
    if hasattr(result, 'num_speakers'):
        data["num_speakers"] = getattr(result, 'num_speakers')

    return json.dumps(data, indent=indent, ensure_ascii=ensure_ascii)

def save_json(result: TranscriptResult, output_path: str, indent: int = 2, ensure_ascii: bool = False) -> None:
    """Save TranscriptResult as JSON file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(to_json(result, indent=indent, ensure_ascii=ensure_ascii))
