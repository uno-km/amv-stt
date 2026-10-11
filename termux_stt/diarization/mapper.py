# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from typing import List, Tuple

from termux_stt.export.result import Segment


class SpeakerMapper:
    """Maps speaker clusters to STT text segments."""

    def __init__(self):
        pass

    def align(self, segments: List[Segment], speaker_labels: List[Tuple[float, float, int]], num_speakers: int = 2) -> List[Segment]:
        """
        Align STT text segments with neural diarization speaker time intervals.
        Assigns the speaker label that overlaps the most with the segment.
        """
        aligned_segments: List[Segment] = []
        if not speaker_labels:
            default_spk = "Speaker_0" if num_speakers == 1 else "Speaker_Unknown"
            for seg in segments:
                aligned_segments.append(Segment(
                    text=seg.text,
                    start=seg.start,
                    end=seg.end,
                    speaker=default_spk
                ))
            return aligned_segments

        # Normalize speaker labels chronologically so the first speaker is always 0
        normalized_labels = self._normalize_speaker_ids(speaker_labels)

        for seg in segments:
            if num_speakers == 1:
                aligned_segments.append(Segment(
                    text=seg.text,
                    start=seg.start,
                    end=seg.end,
                    speaker=self.format_speaker_label(0)
                ))
                continue

            best_speaker = -1
            max_overlap = 0.0

            for spk_start, spk_end, cluster_id in normalized_labels:
                overlap = self._time_overlap(seg.start, seg.end, spk_start, spk_end)
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_speaker = cluster_id

            if best_speaker != -1:
                speaker_name = self.format_speaker_label(best_speaker)
            elif aligned_segments:
                # Inherit preceding segment speaker for trailing punctuation / pauses
                speaker_name = aligned_segments[-1].speaker
            elif normalized_labels:
                speaker_name = self.format_speaker_label(normalized_labels[0][2])
            else:
                speaker_name = self.format_speaker_label(0)

            aligned_segments.append(Segment(
                text=seg.text,
                start=seg.start,
                end=seg.end,
                speaker=speaker_name
            ))

        return aligned_segments

    def _normalize_speaker_ids(self, speaker_labels: List[Tuple[float, float, int]]) -> List[Tuple[float, float, int]]:
        """Normalize cluster IDs in chronological order of appearance (0, 1, 2...)."""
        mapping = {}
        normalized = []
        for start, end, cluster_id in sorted(speaker_labels, key=lambda x: x[0]):
            if cluster_id not in mapping:
                mapping[cluster_id] = len(mapping)
            normalized.append((start, end, mapping[cluster_id]))
        return normalized

    def _time_overlap(self, seg_start: float, seg_end: float, spk_start: float, spk_end: float) -> float:
        """Calculate overlap duration between two time intervals."""
        overlap_start = max(seg_start, spk_start)
        overlap_end = min(seg_end, spk_end)
        return max(0.0, overlap_end - overlap_start)

    def format_speaker_label(self, cluster_id: int) -> str:
        """Format cluster ID into speaker label string."""
        return f"Speaker_{cluster_id}"

    def merge_consecutive(self, segments: List[Segment], max_pause: float = 1.5) -> List[Segment]:
        """Merge consecutive segments from the same speaker into natural utterances."""
        if not segments:
            return []

        merged: List[Segment] = []
        curr = Segment(
            text=segments[0].text,
            start=segments[0].start,
            end=segments[0].end,
            speaker=segments[0].speaker,
            confidence=segments[0].confidence,
        )

        for nxt in segments[1:]:
            if nxt.speaker == curr.speaker and (nxt.start - curr.end) <= max_pause:
                curr_txt = curr.text
                nxt_txt = nxt.text
                if not curr_txt:
                    curr.text = nxt_txt
                elif not nxt_txt:
                    pass
                elif nxt_txt in (".", ",", "!", "?", "...", "~", " "):
                    curr.text = curr_txt.rstrip() + nxt_txt
                elif curr_txt.endswith(" ") or nxt_txt.startswith(" "):
                    curr.text = (curr_txt + nxt_txt).strip()
                else:
                    curr.text = curr_txt + nxt_txt
                curr.end = max(curr.end, nxt.end)
                if curr.confidence is not None and nxt.confidence is not None:
                    curr.confidence = (curr.confidence + nxt.confidence) / 2.0
            else:
                curr.text = curr.text.strip()
                merged.append(curr)
                curr = Segment(
                    text=nxt.text,
                    start=nxt.start,
                    end=nxt.end,
                    speaker=nxt.speaker,
                    confidence=nxt.confidence,
                )
        curr.text = curr.text.strip()
        merged.append(curr)
        return merged
