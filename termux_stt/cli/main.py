# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import argparse
import sys

from termux_stt.cli.benchmark import run_benchmark
from termux_stt.cli.demo import run_demo
from termux_stt.cli.diarize import run_diarize
from termux_stt.cli.doctor import run_doctor
from termux_stt.cli.listen import run_listen
from termux_stt.cli.models_cmd import run_models
from termux_stt.cli.transcribe import run_transcribe
from termux_stt.platform.installer import main as run_install
from termux_stt.web import run_web_app


def _run_cli():
    parser = argparse.ArgumentParser(description="Termux STT - On-device Speech-to-Text Framework")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Common parent parser for shared arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--engine", type=str, default="whisper", choices=["whisper", "hybrid", "sherpa"], help="Engine to use")
    common_parser.add_argument("-m", "--model", type=str, help="Model name or path")
    common_parser.add_argument("-d", "--device", "--backend", "-b", dest="device", type=str, default="auto", choices=["auto", "gpu", "vulkan", "opencl", "cpu"], help="Acceleration device backend (auto, gpu, vulkan, opencl, cpu)")
    common_parser.add_argument("--gpu", dest="device", action="store_const", const="gpu", help="Enable hardware GPU acceleration (alias for -d gpu)")
    common_parser.add_argument("--cpu", dest="device", action="store_const", const="cpu", help="Force CPU compute mode (alias for -d cpu)")
    common_parser.add_argument("--lang", type=str, default="ko", help="Language code")
    common_parser.add_argument("--threads", type=int, default=None, help="Number of CPU threads to use")
    common_parser.add_argument("--vad", action="store_true", help="Enable VAD filtering")
    common_parser.add_argument("--quantization", type=str, choices=["none", "q4_0", "q5_1", "q8_0", "f16"], default="q5_1", help="Model quantization level")
    common_parser.add_argument("--prompt", type=str, default=None, help="Initial prompt / context for decoding")
    common_parser.add_argument("--temperature", type=float, default=None, help="Sampling temperature")
    common_parser.add_argument("--beam-size", "-bs", type=int, default=1, help="Beam search beam size (default: 1 for fast mobile greedy decoding)")
    common_parser.add_argument("--translate", action="store_true", help="Translate source audio to English")
    common_parser.add_argument("--extra-args", type=str, default=None, help="Raw CLI arguments passed directly to the engine")
    common_parser.add_argument("--split-mode", "-sm", "--hybrid", dest="split_mode", action="store_true", default=None, help="Enable hybrid GPU-encoder / CPU-decoder split mode (auto-selected by default on Vulkan)")
    common_parser.add_argument("--no-split-mode", dest="no_split_mode", action="store_true", help="Disable hybrid split mode and force pure GPU execution")
    common_parser.add_argument("--optimize-1", dest="optimize_1", action="store_true", help="Enable hybrid split mode with 1 low-power CPU thread for decoding")
    common_parser.add_argument("--rpc", type=str, default=None, help="Distributed RPC server addresses (e.g. '192.168.0.220:50052,192.168.0.253:50052')")
    common_parser.add_argument("-ts", "--tensor-split", type=str, default=None, help="Fraction of the model to offload across devices (e.g. '50,50' or '60,40')")
    common_parser.add_argument("--cluster-rpc-servers", type=str, default=None, help="AMEVA cluster RPC server endpoints (comma-separated host:port)")
    common_parser.add_argument("--cluster-split-mode", type=str, default=None, help="AMEVA cluster split mode")
    common_parser.add_argument("--cluster-tensor-split", type=str, default=None, help="AMEVA cluster tensor split ratios")
    common_parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    # Install subcommand
    parser_install = subparsers.add_parser("install", help="1-Click automatic installer for native STT engines and neural diarization")
    parser_install.add_argument("-y", "--yes", action="store_true", help="Non-interactive mode flag (retained for script compatibility)")
    parser_install.add_argument("--engine", choices=["whisper", "sherpa", "diarization", "all"], default=None, help="Engine/component to install")
    parser_install.add_argument("--diarization", action="store_true", help="Provision PyAnnote 3.0 & CAM++ diarization models")
    parser_install.add_argument("--all", action="store_true", help="Provision all engines, models, and diarization runtimes")

    # Demo subcommand
    parser_demo = subparsers.add_parser("demo", parents=[common_parser], help="Run zero-configuration STT demo with standard benchmark audio")
    parser_demo.add_argument("--format", type=str, choices=["text", "json", "srt", "vtt"], default="text", help="Output format")
    parser_demo.add_argument("--output", type=str, help="Output file path")

    # Transcribe subcommand
    parser_transcribe = subparsers.add_parser("transcribe", parents=[common_parser], help="Transcribe audio file")
    parser_transcribe.add_argument("file", type=str, nargs="?", default=None, help="Path to audio file (optional if --demo is specified)")
    parser_transcribe.add_argument("--demo", action="store_true", help="Use standard JFK benchmark audio for demonstration")
    parser_transcribe.add_argument("--format", type=str, choices=["text", "json", "srt", "vtt"], default="text", help="Output format")
    parser_transcribe.add_argument("--output", type=str, help="Output file path")

    # Listen subcommand
    parser_listen = subparsers.add_parser("listen", parents=[common_parser], help="Real-time mic transcription")
    parser_listen.add_argument("--duration", type=int, default=0, help="Listen duration in seconds (0 for infinite)")
    parser_listen.add_argument("--diarize", action="store_true", help="Enable online neural speaker diarization")
    parser_listen.add_argument("--speakers", type=int, default=2, help="Expected number of speakers for online diarization")
    parser_listen.add_argument("--chunk-sec", type=float, default=2.0, help="Sliding chunk duration in seconds (default: 2.0)")

    # Live subcommand (live real-time mic streaming with diarization)
    parser_live = subparsers.add_parser("live", parents=[common_parser], help="Real-time live mic listening with online diarization")
    parser_live.add_argument("--duration", type=int, default=0, help="Listen duration in seconds (0 for infinite)")
    parser_live.add_argument("--diarize", action="store_true", default=True, help="Enable online neural speaker diarization")
    parser_live.add_argument("--speakers", type=int, default=2, help="Expected number of speakers for online diarization")
    parser_live.add_argument("--chunk-sec", type=float, default=2.0, help="Sliding chunk duration in seconds (default: 2.0)")

    # App / Web subcommand (browser-based real-time meeting diarizer PWA)
    parser_app = subparsers.add_parser("app", parents=[common_parser], help="Launch on-device real-time meeting diarization Web/PWA App")
    parser_app.add_argument("--host", type=str, default="0.0.0.0", help="HTTP server bind host (default: 0.0.0.0)")
    parser_app.add_argument("--port", type=int, default=8765, help="HTTP server bind port (default: 8765)")
    parser_app.add_argument("--speakers", type=int, default=2, help="Expected number of speakers for online diarization")

    parser_web = subparsers.add_parser("web", parents=[common_parser], help="Alias for 'app' command")
    parser_web.add_argument("--host", type=str, default="0.0.0.0", help="HTTP server bind host (default: 0.0.0.0)")
    parser_web.add_argument("--port", type=int, default=8765, help="HTTP server bind port (default: 8765)")
    parser_web.add_argument("--speakers", type=int, default=2, help="Expected number of speakers for online diarization")

    # Diarize subcommand
    parser_diarize = subparsers.add_parser("diarize", parents=[common_parser], help="Diarize and transcribe audio file")
    parser_diarize.add_argument("file", type=str, help="Path to audio file")
    parser_diarize.add_argument("--speakers", type=int, default=2, help="Number of expected speakers")
    parser_diarize.add_argument("--format", type=str, choices=["text", "json", "rttm"], default="text", help="Output format")
    parser_diarize.add_argument("--speed-mode", type=str, choices=["accurate", "balanced", "fast"], default="balanced", help="Diarization latency profile: balanced (default, 2.5x speedup), fast (4x speedup), accurate")
    parser_diarize.add_argument("--window-shift-ratio", type=float, help="Explicit PyAnnote segmentation window shift ratio (0 < ratio <= 1.0)")
    parser_diarize.add_argument("--output", type=str, help="Output file path")

    # Models subcommand
    parser_models = subparsers.add_parser("models", help="Manage STT models")
    parser_models.add_argument("action", choices=["list", "download", "remove"], help="Action to perform")
    parser_models.add_argument("extra_args", nargs="*", help="Optional positional [engine] [model]")
    parser_models.add_argument("--model", type=str, help="Model name")
    parser_models.add_argument("--engine", type=str, default="whisper", help="Target engine")

    # Doctor subcommand
    subparsers.add_parser("doctor", help="Check system environment and dependencies")

    # Benchmark subcommand
    parser_benchmark = subparsers.add_parser("benchmark", parents=[common_parser], help="Run performance benchmarks")
    parser_benchmark.add_argument("--audio", type=str, required=True, help="Test audio file path")

    # ── AMEVA Component Protocol v1 ─────────────────────────────────────────
    _protocol_available = False
    try:
        from ameva_component.cli_support import build_protocol_subcommands
        build_protocol_subcommands(subparsers)
        _protocol_available = True
    except ImportError as _imp_err:
        import logging
        logging.getLogger(__name__).debug("ameva_component CLI support not installed: %s", _imp_err)
    # ────────────────────────────────────────────────────────────────────────

    args = parser.parse_args()
    args._explicit_lang = any(arg.startswith("--lang") for arg in sys.argv)

    if args.command == "install":
        run_install(args)
    elif args.command == "demo":
        run_demo(args)
    elif args.command == "transcribe":
        if getattr(args, "demo", False):
            from termux_stt.cli.demo import ensure_demo_audio
            args.file = ensure_demo_audio()
            if getattr(args, "lang", None) == "ko" and not args._explicit_lang:
                args.lang = "en"
        elif not args.file:
            parser_transcribe.error("the following arguments are required: file (or use --demo)")
        run_transcribe(args)
    elif args.command in ("listen", "live"):
        run_listen(args)
    elif args.command == "diarize":
        run_diarize(args)
    elif args.command in ("app", "web"):
        run_web_app(args)
    elif args.command == "models":
        run_models(args)
    elif args.command == "doctor":
        run_doctor(args)
    elif args.command == "benchmark":
        run_benchmark(args)
    elif args.command in ("component", "model", "instance") and _protocol_available:
        from ameva_component.cli_support import dispatch_protocol
        from termux_stt.control import STTControl
        dispatch_protocol(args, STTControl())
    elif args.command in ("component", "model", "instance"):
        print("[ERROR] ameva-component-sdk not installed.", file=sys.stderr)
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


def main():
    try:
        _run_cli()
    except FileNotFoundError as e:
        filename = getattr(e, "filename", None) or str(e)
        print(f"\n[-] Error: Input audio file not found -> '{filename}'")
        print("    Please check the file path and ensure the audio file exists.")
        sys.exit(1)
    except PermissionError as e:
        filename = getattr(e, "filename", None) or str(e)
        print(f"\n[-] Error: Permission denied -> '{filename}'")
        print("    (Tip: On Android Termux, root '/tmp' is read-only. Please use a local path like './output.srt')")
        sys.exit(1)
    except ValueError as e:
        print(f"\n[-] Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        from termux_stt.exceptions import TermuxSTTError
        if isinstance(e, TermuxSTTError):
            print(f"\n{e}")
            sys.exit(getattr(e, "code", 1) if isinstance(getattr(e, "code", None), int) else 1)
        if "--verbose" in sys.argv:
            import traceback
            traceback.print_exc()
        else:
            print(f"\n[-] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

