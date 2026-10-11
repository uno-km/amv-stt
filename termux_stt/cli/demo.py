# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Demo subcommand for termux-stt.
Provides a zero-configuration demonstration using on-demand sample audio.
"""

import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from termux_stt.cli.transcribe import run_transcribe
from termux_stt.exceptions import RuntimeRequiredError

PRIMARY_SAMPLE_URL = "https://raw.githubusercontent.com/uno-km/termux-stt/main/samples/jfk_1min.wav"
FALLBACK_SAMPLE_URL = "https://raw.githubusercontent.com/uno-km/uno-km/main/lib/forge/samples/jfk_1min.wav"
EXPECTED_MIN_BYTES = 1000000  # ~1.92 MB expected


def ensure_demo_audio() -> str:
    """
    Locates or retrieves the standard 1-minute JFK benchmark audio file.
    
    Order of discovery:
    1. Local repository path: `samples/jfk_1min.wav`
    2. User cache path: `~/.cache/termux-stt/samples/jfk_1min.wav`
    3. Remote download via HTTPS to user cache
    
    Returns:
        Absolute path to the verified audio file.
    """
    # 1. Local repository check
    repo_sample = Path(__file__).resolve().parent.parent.parent / "samples" / "jfk_1min.wav"
    if repo_sample.is_file() and repo_sample.stat().st_size >= EXPECTED_MIN_BYTES:
        return str(repo_sample)

    cwd_sample = Path.cwd() / "samples" / "jfk_1min.wav"
    if cwd_sample.is_file() and cwd_sample.stat().st_size >= EXPECTED_MIN_BYTES:
        return str(cwd_sample)

    # 2. Cache directory check
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "termux-stt" / "samples"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_file = cache_dir / "jfk_1min.wav"

    if cached_file.is_file() and cached_file.stat().st_size >= EXPECTED_MIN_BYTES:
        return str(cached_file)

    # 3. On-demand download
    print("[*] Demo audio not found locally. Downloading standard benchmark audio (jfk_1min.wav)...")
    download_urls = [PRIMARY_SAMPLE_URL, FALLBACK_SAMPLE_URL]
    download_success = False
    last_error = None

    for url in download_urls:
        try:
            print(f"[*] Fetching: {url}")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "termux-stt-demo/1.1.8"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                if len(data) >= EXPECTED_MIN_BYTES:
                    with open(cached_file, "wb") as f:
                        f.write(data)
                    download_success = True
                    print(f"[+] Successfully cached benchmark audio to: {cached_file} ({len(data):,} bytes)")
                    break
                else:
                    last_error = f"Incomplete download ({len(data)} bytes)"
        except RuntimeRequiredError:
            raise
        except Exception as err:
            last_error = err
            print(f"[-] Mirror fetch failed ({url}): {err}")

    if not download_success or not cached_file.is_file():
        print(f"[!] Error: Failed to acquire demo audio file: {last_error}", file=sys.stderr)
        print("    You can manually provide an audio file via: termux-stt transcribe <audio_file>", file=sys.stderr)
        sys.exit(1)

    return str(cached_file)


def run_demo(args):
    """
    Executes an out-of-the-box STT demo on the JFK benchmark audio.
    """
    audio_path = ensure_demo_audio()
    args.file = audio_path

    # If language was left as default 'ko', switch to 'en' for JFK speech unless explicitly specified
    if getattr(args, "lang", None) == "ko" and not getattr(args, "_explicit_lang", False):
        args.lang = "en"

    print("=" * 60)
    print("  termux-stt :: Zero-Configuration Demo")
    print(f"  Target Audio : {audio_path}")
    print(f"  Language     : {args.lang}")
    print(f"  Engine       : {args.engine}")
    print("=" * 60)

    run_transcribe(args)
