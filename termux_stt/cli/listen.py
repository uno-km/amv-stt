# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import time

from termux_stt import create_engine


def run_listen(args):
    engine_name = getattr(args, "engine", "hybrid" if getattr(args, "diarize", False) else "whisper")
    num_speakers = getattr(args, "speakers", 2)
    chunk_sec = getattr(args, "chunk_sec", 2.0)
    enable_diarize = getattr(args, "diarize", False)

    engine = create_engine(
        engine=engine_name,
        model=getattr(args, "model", None),
        lang=getattr(args, "lang", "ko"),
        threads=getattr(args, "threads", None),
        vad=getattr(args, "vad", True),
        num_speakers=num_speakers if enable_diarize else None,
    )

    if enable_diarize:
        print(f"Listening with {engine_name} [Real-time Online Diarization: {num_speakers} speakers]... (Press Ctrl+C to stop)")
    else:
        print(f"Listening with {engine_name}... (Press Ctrl+C to stop)")

    start_time = time.time()

    try:
        if enable_diarize and hasattr(engine, "stream_mic_diarize"):
            stream = engine.stream_mic_diarize(
                duration=args.duration if args.duration > 0 else None,
                chunk_sec=chunk_sec,
                num_speakers=num_speakers,
            )
        else:
            stream = engine.stream_mic(
                duration=args.duration if args.duration > 0 else None
            )

        for segment in stream:
            spk_tag = f"[{segment.speaker}] " if getattr(segment, "speaker", None) else ""
            print(f"[{segment.start:.2f} - {segment.end:.2f}] {spk_tag}{segment.text}")
            if args.duration > 0 and (time.time() - start_time) >= args.duration:
                print(f"Reached duration limit of {args.duration} seconds.")
                break
    except KeyboardInterrupt:
        print("\nStopped listening.")

