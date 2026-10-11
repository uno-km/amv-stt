# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""Lightweight zero-dependency Web & PWA server for live STT and online diarization."""

import io
import json
import logging
import math
import os
import queue
import socket
import struct
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = ["STTWebAppServer", "run_web_app"]


class STTSession:
    """Manages active live recording session and connected browser event clients."""

    def __init__(self, engine_name: str = "hybrid", model: Optional[str] = None, lang: str = "ko", num_speakers: int = 2) -> None:
        self.engine_name = engine_name
        self.model = model
        self.lang = lang
        self.num_speakers = num_speakers

        self.is_recording = False
        self.audio_source = "device"  # 'device' or 'browser'
        self.start_time: Optional[float] = None
        self.history: List[Dict[str, Any]] = []
        self.speaker_names: Dict[str, str] = {}
        self.active_speakers: set = set()

        self.clients: List[queue.Queue] = []
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Audio ingestion queue for browser streaming
        self.audio_buffer = queue.Queue()

        # Engine & Diarizer
        self._diarizer = None
        self._engine = None
        self._init_engine()

    def _init_engine(self) -> None:
        try:
            from termux_stt import create_engine
            from termux_stt.diarization.online_diarizer import OnlineSpeakerDiarizer

            self._diarizer = OnlineSpeakerDiarizer(
                num_speakers=self.num_speakers,
                sample_rate=16000,
                threshold=0.60,
                threads=4,
            )
            self._engine = create_engine(
                engine=self.engine_name,
                model=self.model or "tiny",
                lang=self.lang,
                threads=4,
                num_speakers=self.num_speakers,
            )
            logger.info("STTSession: Engine & Diarizer initialized successfully")
        except Exception as exc:
            logger.error("STTSession: Failed to initialize STT engine: %s", exc)

    def add_client(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self._lock:
            self.clients.append(q)
        return q

    def remove_client(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self.clients:
                self.clients.remove(q)

    def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        payload = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        with self._lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    pass

    def rename_speaker(self, old_name: str, new_name: str) -> None:
        with self._lock:
            self.speaker_names[old_name] = new_name
            for seg in self.history:
                if seg.get("raw_speaker") == old_name:
                    seg["speaker"] = new_name
        self.broadcast("speaker_renamed", {"old_name": old_name, "new_name": new_name})

    def start_recording(self, source: str = "device") -> None:
        if self.is_recording:
            return
        self.is_recording = True
        self.audio_source = source
        self.start_time = time.time()
        self._stop_event.clear()

        if source == "device":
            self._worker_thread = threading.Thread(target=self._device_record_loop, daemon=True)
            self._worker_thread.start()
        elif source == "browser":
            self._worker_thread = threading.Thread(target=self._browser_audio_loop, daemon=True)
            self._worker_thread.start()

        self.broadcast("session_state", {"is_recording": True, "source": source})

    def stop_recording(self) -> None:
        if not self.is_recording:
            return
        self.is_recording = False
        self._stop_event.set()
        self.broadcast("session_state", {"is_recording": False})

    def ingest_browser_audio(self, pcm_bytes: bytes) -> None:
        if self.is_recording and self.audio_source == "browser":
            self.audio_buffer.put(pcm_bytes)

    def _process_audio_chunk(self, pcm_bytes: bytes, start_sec: float, end_sec: float) -> None:
        if not self._diarizer or not self._engine:
            return

        # 1. Online Diarization
        spk_seg = self._diarizer.process_chunk(pcm_bytes, start_sec=start_sec, end_sec=end_sec)
        if not spk_seg.is_speech:
            return

        raw_spk = spk_seg.speaker
        disp_spk = self.speaker_names.get(raw_spk, raw_spk)
        self.active_speakers.add(raw_spk)

        # 2. Transcribe Chunk
        import tempfile
        import wave
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm_bytes)

        text = ""
        try:
            whisper_eng = getattr(self._engine, "_whisper", self._engine)
            res = whisper_eng.transcribe(tmp_path)
            text = res.text.strip()
        except Exception as exc:
            logger.debug("Transcribe chunk error: %s", exc)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        if text:
            record = {
                "id": len(self.history) + 1,
                "start": round(start_sec, 2),
                "end": round(end_sec, 2),
                "raw_speaker": raw_spk,
                "speaker": disp_spk,
                "text": text,
                "confidence": round(spk_seg.confidence, 2),
                "timestamp": time.strftime("%H:%M:%S"),
            }
            with self._lock:
                self.history.append(record)
            self.broadcast("segment", record)

    def _device_record_loop(self) -> None:
        from termux_stt.audio.mic import MicCapture
        mic = MicCapture()
        chunk_sec = 2.0
        time_offset = 0.0

        stream_iter = (
            mic.stream_continuous(chunk_sec=chunk_sec)
            if hasattr(mic, "stream_continuous")
            else mic.stream(chunk_sec=chunk_sec)
        )

        for chunk_bytes in stream_iter:
            if self._stop_event.is_set():
                break
            dur = len(chunk_bytes) / (16000 * 2)
            self._process_audio_chunk(chunk_bytes, time_offset, time_offset + dur)
            time_offset += dur

    def _browser_audio_loop(self) -> None:
        chunk_sec = 2.0
        bytes_needed = int(16000 * 2 * chunk_sec)
        accumulator = bytearray()
        time_offset = 0.0

        while not self._stop_event.is_set():
            try:
                data = self.audio_buffer.get(timeout=0.5)
                accumulator.extend(data)
                while len(accumulator) >= bytes_needed:
                    chunk = bytes(accumulator[:bytes_needed])
                    del accumulator[:bytes_needed]
                    self._process_audio_chunk(chunk, time_offset, time_offset + chunk_sec)
                    time_offset += chunk_sec
            except queue.Empty:
                continue

    def export_text(self, fmt: str = "txt") -> str:
        with self._lock:
            items = list(self.history)

        if fmt == "srt":
            lines = []
            for i, item in enumerate(items, 1):
                s_h, s_m = divmod(int(item["start"]), 3600)
                s_m, s_s = divmod(s_m, 60)
                s_ms = int((item["start"] % 1) * 1000)

                e_h, e_m = divmod(int(item["end"]), 3600)
                e_m, e_s = divmod(e_m, 60)
                e_ms = int((item["end"] % 1) * 1000)

                lines.append(f"{i}")
                lines.append(f"{s_h:02d}:{s_m:02d}:{s_s:02d},{s_ms:03d} --> {e_h:02d}:{e_m:02d}:{e_s:02d},{e_ms:03d}")
                lines.append(f"[{item['speaker']}] {item['text']}\n")
            return "\n".join(lines)
        elif fmt == "json":
            return json.dumps(items, ensure_ascii=False, indent=2)
        else:
            return "\n".join(f"[{item['timestamp']}] [{item['speaker']}]: {item['text']}" for item in items)


class WebAppHandler(BaseHTTPRequestHandler):
    """HTTP & SSE Request handler for termux-stt Web/PWA App."""

    session: STTSession = None
    static_dir: str = ""

    def log_message(self, format, *args):
        # Suppress noisy access log in standard console
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._serve_file(os.path.join(self.static_dir, "index.html"), "text/html; charset=utf-8")
        elif path == "/manifest.json":
            self._serve_manifest()
        elif path == "/api/events":
            self._serve_sse()
        elif path == "/api/status":
            self._json_response({
                "is_recording": self.session.is_recording,
                "audio_source": self.session.audio_source,
                "duration": round(time.time() - self.session.start_time, 1) if self.session.start_time else 0,
                "history_count": len(self.session.history),
                "speakers": sorted(list(self.session.active_speakers)),
                "speaker_names": self.session.speaker_names,
            })
        elif path == "/api/export":
            query = urllib.parse.parse_qs(parsed.query)
            fmt = query.get("format", ["txt"])[0]
            content = self.session.export_text(fmt)
            ext = fmt if fmt in ("srt", "json") else "txt"
            mime = "application/json" if fmt == "json" else "text/plain; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f"attachment; filename=meeting_transcript.{ext}")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))

        if path == "/api/mic/start":
            body = self.rfile.read(length) if length > 0 else b"{}"
            data = json.loads(body.decode("utf-8") or "{}")
            source = data.get("source", "device")
            self.session.start_recording(source=source)
            self._json_response({"ok": True, "is_recording": True, "source": source})

        elif path == "/api/mic/stop":
            self.session.stop_recording()
            self._json_response({"ok": True, "is_recording": False})

        elif path == "/api/stream_audio":
            # Direct binary PCM upload from browser WebAudio API
            pcm_bytes = self.rfile.read(length)
            self.session.ingest_browser_audio(pcm_bytes)
            self._json_response({"ok": True, "bytes": len(pcm_bytes)})

        elif path == "/api/rename_speaker":
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            self.session.rename_speaker(data["old_name"], data["new_name"])
            self._json_response({"ok": True})

        elif path == "/api/clear":
            with self.session._lock:
                self.session.history.clear()
            self.session.broadcast("history_cleared", {})
            self._json_response({"ok": True})

        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _serve_file(self, filepath: str, mime: str) -> None:
        if not os.path.exists(filepath):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_manifest(self) -> None:
        manifest = {
            "name": "Termux STT Live Diarizer",
            "short_name": "STT Live",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#0ea5e9",
            "icons": [
                {
                    "src": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%230ea5e9'%3E%3Cpath d='M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z'/%3E%3Cpath d='M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z'/%3E%3C/svg%3E",
                    "sizes": "192x192 512x512",
                    "type": "image/svg+xml"
                }
            ]
        }
        self._json_response(manifest)

    def _serve_sse(self) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send initial history
        with self.session._lock:
            init_data = {
                "is_recording": self.session.is_recording,
                "history": self.session.history,
                "speaker_names": self.session.speaker_names,
            }
        init_payload = f"event: init\ndata: {json.dumps(init_data, ensure_ascii=False)}\n\n"
        self.wfile.write(init_payload.encode("utf-8"))
        self.wfile.flush()

        q = self.session.add_client()
        try:
            while True:
                try:
                    msg = q.get(timeout=15.0)
                    self.wfile.write(msg.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Keep-alive heartbeat
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            self.session.remove_client(q)

    def _json_response(self, obj: Any) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


class STTWebAppServer:
    """Manages the lifecycle of the Termux STT Web App server."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        engine: str = "hybrid",
        model: Optional[str] = None,
        lang: str = "ko",
        num_speakers: int = 2,
    ) -> None:
        self.host = host
        self.port = port
        self.session = STTSession(engine_name=engine, model=model, lang=lang, num_speakers=num_speakers)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.static_dir = os.path.join(current_dir, "static")
        os.makedirs(self.static_dir, exist_ok=True)

        WebAppHandler.session = self.session
        WebAppHandler.static_dir = self.static_dir

        self.httpd = ThreadingHTTPServer((self.host, self.port), WebAppHandler)

    def start(self) -> None:
        print("=" * 65)
        print(" [Termux STT Live Web/PWA App] Server Running")
        print("=" * 65)
        print(f" • Local Access:    http://localhost:{self.port}")
        print(f" • Network Access:  http://{self._get_lan_ip()}:{self.port}")
        print(f" • Engine Profile:  {self.session.engine_name} ({self.session.lang})")
        print(f" • Max Speakers:    {self.session.num_speakers}")
        print("=" * 65)
        print("Press Ctrl+C to terminate.")

        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Termux STT Web App...")
        finally:
            self.session.stop_recording()
            self.httpd.server_close()

    def _get_lan_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


def run_web_app(args: Any) -> None:
    server = STTWebAppServer(
        host=getattr(args, "host", "0.0.0.0"),
        port=getattr(args, "port", 8765),
        engine=getattr(args, "engine", "hybrid"),
        model=getattr(args, "model", None),
        lang=getattr(args, "lang", "ko"),
        num_speakers=getattr(args, "speakers", 2),
    )
    server.start()
