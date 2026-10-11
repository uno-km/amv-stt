# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import json
from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class TranscriptResult:
    text: str
    segments: List[Segment]
    language: Optional[str] = None
    duration: Optional[float] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    def to_srt(self) -> str:
        res = []
        for i, seg in enumerate(self.segments):
            res.append(str(i + 1))
            res.append(f"{self._format_time(seg.start)} --> {self._format_time(seg.end)}")
            res.append(seg.text)
            res.append("")
        return "\n".join(res)

    def to_vtt(self) -> str:
        res = ["WEBVTT\n"]
        for seg in self.segments:
            res.append(f"{self._format_time(seg.start, vtt=True)} --> {self._format_time(seg.end, vtt=True)}")
            res.append(seg.text)
            res.append("")
        return "\n".join(res)

    def to_rttm(self) -> str:
        res = []
        for seg in self.segments:
            speaker = seg.speaker or "SPEAKER_00"
            duration = seg.end - seg.start
            res.append(f"SPEAKER file 1 {seg.start:.2f} {duration:.2f} <NA> <NA> {speaker} <NA> <NA>")
        return "\n".join(res)

    @staticmethod
    def _format_time(seconds: float, vtt: bool = False) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        sep = "." if vtt else ","
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", sep)


@dataclass
class DiarizedResult(TranscriptResult):
    speakers: Optional[List[str]] = None
