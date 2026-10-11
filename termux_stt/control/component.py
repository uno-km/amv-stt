# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
termux_stt.control.component
AMEVA Component Protocol v1 — STTControl

기존 cli/doctor.py + models/registry.py를 Adapter로 연결합니다.
Primary(whisper/vosk/sherpa) + Optional(VAD, Diarization) 분리 추적.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from ameva_component import (
    ActivationLock,
    ComponentInfo,
    ComponentStateFile,
    ControlMode,
    InstanceRegistry,
    InstanceState,
    InstanceStatus,
    ModelRegistry,
    ModelState,
    OperationNotSupported,
    ModelNotFound,
    ModelLoadFailed,
    now_timestamps,
    log_stderr,
    PROTOCOL_COMPONENT,
)
from ameva_component.control import ComponentControl


class STTControl(ComponentControl):
    """
    termux-stt ComponentControl.

    기존 cli/doctor.py, models/registry.py, models/hub.py를 Adapter로 연결합니다.
    하드코딩 ready=true 절대 금지.
    """

    COMPONENT_ID   = "termux-stt"
    COMPONENT_TYPE = "stt"
    # audio.translate, audio.diarize, audio.vad는 옵션 의존성 확인 후 활성화
    CAPABILITIES   = ("audio.transcribe",)

    DEFAULT_CACHE_DIR = Path.home() / ".cache" / "termux-stt"
    DEFAULT_PID_FILE  = Path.home() / ".local" / "run" / "termux-stt.pid"

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir  = cache_dir or self.DEFAULT_CACHE_DIR
        self._state_file = ComponentStateFile(self.COMPONENT_ID)
        self._model_reg  = ModelRegistry(self.COMPONENT_ID)
        self._inst_reg   = InstanceRegistry(self.COMPONENT_ID)
        self._act_lock   = ActivationLock()
        # Phase 4: Heartbeat Writer
        from termux_stt.control.status import STTStatusWriter
        self._heartbeat = STTStatusWriter(self)

    def _get_version(self) -> str:
        try:
            from termux_stt import __version__
            return __version__
        except Exception:
            return "1.1.6"

    # ------------------------------------------------------------------
    # 1. component_info
    # ------------------------------------------------------------------

    def component_info(self) -> dict:
        info = ComponentInfo(
            protocol=PROTOCOL_COMPONENT,
            component_id=self.COMPONENT_ID,
            component_type=self.COMPONENT_TYPE,
            version=self._get_version(),
            capabilities=self.CAPABILITIES,
        )
        info.validate()
        return info.to_dict()

    # ------------------------------------------------------------------
    # 2. doctor_lite — 500ms 이내
    # ------------------------------------------------------------------

    def doctor_lite(self) -> dict:
        """
        경량 상태 확인.
        기존 cli/doctor.py의 run_doctor()는 doctor_full()에서만 호출.
        여기서는 상태 파일 + PID + 활성 모델만 확인.
        """
        ts = now_timestamps()
        state_data = self._state_file.read()
        stale = self._state_file.is_stale(threshold_ms=30_000)
        pid_info = self._check_pid()
        pid = pid_info.get("pid")
        pid_alive = pid_info.get("alive")

        instances = self._inst_reg.list_all()
        hot = [i for i in instances if i.state == InstanceState.HOT]
        active_models = list({i.model_id for i in hot})
        total_active_jobs = sum(i.active_jobs for i in instances)

        # 엔진 가용 여부 (import 성공 여부만 — 실제 로드 금지)
        engines_available = self._check_engines_available()

        ready = (pid_alive is True) and not stale and bool(engines_available)
        degraded = stale or (pid_alive is not True) or not engines_available

        proc_dict: dict[str, Any] = {
            "running": pid_alive,
            "pid": pid,
            "verified": pid_info.get("verified", False),
        }
        if "inspection_error" in pid_info:
            proc_dict["inspection_error"] = pid_info["inspection_error"]
        if "reason" in pid_info:
            proc_dict["reason"] = pid_info["reason"]

        return {
            "protocol":         "ameva-component-status/1",
            "component_id":     self.COMPONENT_ID,
            "component_type":   self.COMPONENT_TYPE,
            "version":          self._get_version(),
            "ready":            ready,
            "degraded":         degraded,
            **ts,
            "process":          proc_dict,
            "capabilities":     list(self.CAPABILITIES),
            "active_models":    active_models,
            "engines_available": engines_available,
            "instances":        [
                {"instance_id": i.instance_id, "model_id": i.model_id,
                 "state": i.state.value, "active_jobs": i.active_jobs}
                for i in instances
            ],
            "errors":           [state_data.get("last_error")] if state_data and state_data.get("last_error") else [],
            "state_file":       {
                "path":       str(self._state_file.path),
                "stale":      stale,
                "updated_at": state_data.get("updated_at") if state_data else None,
            },
        }

    def _check_pid(self) -> dict[str, Any]:
        """BLOCKER 1: PID 파일과 상태 파일 기반 프로세스 활성 여부 확인.
        PermissionError/OSError 발생 시 alive=None, verified=False, inspection_error 반환."""
        import logging
        _log = logging.getLogger(__name__)

        if self.DEFAULT_PID_FILE.exists():
            try:
                raw = self.DEFAULT_PID_FILE.read_text().strip()
                pid = int(raw)
            except (ValueError, OSError) as parse_err:
                _log.warning("[stt] PID file parse/read error: %s", parse_err)
                return {
                    "pid": None,
                    "alive": None,
                    "verified": False,
                    "inspection_error": {
                        "code": "PID_PARSE_ERROR",
                        "message": str(parse_err),
                    },
                }

            try:
                os.kill(pid, 0)
                return {"pid": pid, "alive": True, "verified": True}
            except ProcessLookupError:
                return {
                    "pid": pid,
                    "alive": False,
                    "verified": True,
                    "reason": "process_lookup_failed",
                }
            except PermissionError as perm_err:
                _log.warning("[stt] PID file PID alive check PermissionError: %s", perm_err)
                return {
                    "pid": pid,
                    "alive": None,
                    "verified": False,
                    "inspection_error": {
                        "code": "PROCESS_INSPECTION_PERMISSION_DENIED",
                        "message": str(perm_err),
                    },
                }
            except OSError as os_err:
                _log.warning("[stt] PID file PID alive check OSError: %s", os_err)
                return {
                    "pid": pid,
                    "alive": None,
                    "verified": False,
                    "inspection_error": {
                        "code": "PROCESS_INSPECTION_OS_ERROR",
                        "message": str(os_err),
                    },
                }

        state_data = self._state_file.read()
        if state_data:
            pid = state_data.get("process", {}).get("pid")
            if pid:
                try:
                    os.kill(pid, 0)
                    return {"pid": pid, "alive": True, "verified": True}
                except ProcessLookupError:
                    return {
                        "pid": pid,
                        "alive": False,
                        "verified": True,
                        "reason": "process_lookup_failed",
                    }
                except PermissionError as perm_err:
                    _log.warning("[stt] State-file PID %d PermissionError: %s", pid, perm_err)
                    return {
                        "pid": pid,
                        "alive": None,
                        "verified": False,
                        "inspection_error": {
                            "code": "PROCESS_INSPECTION_PERMISSION_DENIED",
                            "message": str(perm_err),
                        },
                    }
                except OSError as os_err:
                    _log.warning("[stt] State-file PID %d OSError: %s", pid, os_err)
                    return {
                        "pid": pid,
                        "alive": None,
                        "verified": False,
                        "inspection_error": {
                            "code": "PROCESS_INSPECTION_OS_ERROR",
                            "message": str(os_err),
                        },
                    }

        return {
            "pid": None,
            "alive": False,
            "verified": True,
            "reason": "pid_file_missing",
        }

    def _check_engines_available(self) -> dict:
        """실제 모듈 import 가능 여부만 확인 — 로드/추론 금지."""
        result = {}
        for engine_name, module in [
            ("whisper", "termux_stt.engine.whisper_engine"),
            ("vosk",    "termux_stt.engine.vosk_engine"),
            ("sherpa",  "termux_stt.engine.sherpa_engine"),
        ]:
            try:
                __import__(module)
                result[engine_name] = True
            except ImportError:
                result[engine_name] = False
        return result

    # ------------------------------------------------------------------
    # 3. doctor_full
    # ------------------------------------------------------------------

    def doctor_full(self) -> dict:
        """기존 cli/doctor.py run_doctor()를 호출하여 상세 진단."""
        lite = self.doctor_lite()
        try:
            import io, contextlib
            from termux_stt.cli.doctor import run_doctor
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                run_doctor(type("args", (), {})())
            lite["doctor_output"] = buf.getvalue()
        except Exception as e:
            lite["doctor_error"] = str(e)
        lite["doctor_level"] = "full"
        return lite

    # ------------------------------------------------------------------
    # 4. list_models
    # ------------------------------------------------------------------

    def list_models(self) -> dict:
        """기존 models/hub.py + models/registry.py + AMEVA ModelRegistry 통합."""
        reg_models = self._model_reg.list_all()
        reg_map = {m["model_id"]: m for m in reg_models}

        # 기존 ModelHub 캐시 통합
        try:
            from termux_stt.models.hub import ModelHub
            for item in ModelHub.list_cached_models():
                model_id = f"{item.get('engine', 'unknown')}/{item.get('model_name', 'unknown')}"
                if model_id not in reg_map:
                    reg_map[model_id] = {
                        "model_id":    model_id,
                        "state":       "unverified",
                        "engine":      item.get("engine"),
                        "model_name":  item.get("model_name"),
                        "note":        "In local cache but not verified by AMEVA registry",
                        "verified_at": None,
                    }
        except Exception as e:
            log_stderr(f"[stt] ModelHub list failed: {e}")

        return {
            "models":    list(reg_map.values()),
            "total":     len(reg_map),
            "cache_dir": str(self._cache_dir),
        }

    # ------------------------------------------------------------------
    # 5. model_status
    # ------------------------------------------------------------------

    def model_status(self, model_id: str | None = None) -> dict:
        if model_id:
            rec = self._model_reg.get(model_id)
            if rec is None:
                raise ModelNotFound(model_id)
            return {"model": rec}
        return self.list_models()

    # ------------------------------------------------------------------
    # 6. install_model
    # ------------------------------------------------------------------

    def install_model(self, request: dict) -> dict:
        from ameva_component import ModelInstaller
        url            = request.get("url", "")
        filename       = request.get("filename", "")
        sha256         = request.get("sha256", "")
        expected_bytes = int(request.get("expected_bytes", 0))
        model_id       = request.get("model_id") or Path(filename).stem

        dest = self._cache_dir / "models"
        dest.mkdir(parents=True, exist_ok=True)
        installer = ModelInstaller(self.COMPONENT_ID, dest, self._model_reg)
        return installer.install(
            url=url, filename=filename, sha256=sha256,
            expected_bytes=expected_bytes, model_id=model_id,
            after_download=self._verify_audio_model,
        )

    def _verify_audio_model(self, path: Path) -> None:
        """오디오 모델 기본 형식 확인 — 모델 로드 금지."""
        suffix = path.suffix.lower()
        valid_suffixes = {".bin", ".pt", ".onnx", ".tflite", ".gguf"}
        if suffix not in valid_suffixes:
            raise ValueError(f"Unexpected model format: '{suffix}'. Expected one of {valid_suffixes}")

    # ------------------------------------------------------------------
    # 7-8. activate/deactivate_model
    # ------------------------------------------------------------------

    async def activate_model(self, request: dict) -> dict:
        model_id = request.get("model_id", "")
        rec = self._model_reg.get(model_id)
        if rec is None:
            raise ModelNotFound(model_id)
        if ModelState.from_str(rec.get("state", "missing")) not in (
            ModelState.INSTALLED, ModelState.INACTIVE
        ):
            raise ModelLoadFailed(model_id, f"State is '{rec.get('state')}', not activatable")

        prev_active = None
        with self._act_lock.acquire(timeout=60.0):
            hot = [i for i in self._inst_reg.list_all() if i.state == InstanceState.HOT]
            prev_active = hot[0].model_id if hot else None
            try:
                self._model_reg.set_state(model_id, ModelState.ACTIVATING)
                # 파일 존재 확인만 (실제 엔진 로드 금지)
                if not self._find_model_file(model_id):
                    raise ModelLoadFailed(model_id, "Model file not found")
                self._model_reg.set_state(model_id, ModelState.ACTIVE)
                if prev_active and prev_active != model_id:
                    self._model_reg.set_state(prev_active, ModelState.INACTIVE)
                self._write_state()
                return {"activated": True, "model_id": model_id,
                        "rollback": {"attempted": False, "succeeded": False}}
            except Exception as exc:
                if prev_active:
                    self._model_reg.set_state(prev_active, ModelState.ACTIVE)
                self._model_reg.set_state(model_id, ModelState.FAILED, last_error=str(exc))
                self._write_state(ready=False, last_error=str(exc))
                return {"activated": False, "model_id": model_id,
                        "rollback": {"attempted": True, "succeeded": True},
                        "errors": [str(exc)]}

    def _find_model_file(self, model_id: str) -> Path | None:
        for ext in [".bin", ".pt", ".onnx", ".gguf", ".tflite"]:
            p = self._cache_dir / "models" / f"{model_id}{ext}"
            if p.exists():
                return p
        return None

    async def deactivate_model(self, request: dict) -> dict:
        model_id = request.get("model_id", "")
        self._model_reg.set_state(model_id, ModelState.INACTIVE)
        self._write_state()
        return {"deactivated": True, "model_id": model_id}

    # ------------------------------------------------------------------
    # 9-12. Instance 관리
    # ------------------------------------------------------------------

    def list_instances(self) -> dict:
        instances = self._inst_reg.list_all()
        return {"instances": [i.to_dict() for i in instances], "total": len(instances)}

    async def start_instance(self, request: dict) -> dict:
        model_id = request.get("model_id", "")
        instance_id = request.get("instance_id") or f"stt-worker-{int(time.time())}"
        inst = InstanceStatus(
            instance_id=instance_id, component_id=self.COMPONENT_ID,
            model_id=model_id, state=InstanceState.HOT,
            active_jobs=0, queue_depth=0, max_concurrency=1,
            backend="cpu", started_at=time.time(), last_heartbeat=time.time(),
            last_error=None, control_mode=ControlMode.IN_PROCESS,
        )
        self._inst_reg.register(inst)
        self._write_state()
        # Phase 4: Heartbeat 시작 (Worker 시작 트리거)
        self._heartbeat.start()
        return {"instance_id": instance_id, "state": InstanceState.HOT.value}

    async def drain_instance(self, instance_id: str) -> dict:
        from ameva_component import InstanceNotFound
        if not self._inst_reg.get(instance_id):
            raise InstanceNotFound(instance_id)
        self._inst_reg.update_state(instance_id, InstanceState.DRAINING)
        return {"instance_id": instance_id, "state": InstanceState.DRAINING.value}

    async def stop_instance(self, instance_id: str) -> dict:
        from ameva_component import InstanceNotFound
        if not self._inst_reg.get(instance_id):
            raise InstanceNotFound(instance_id)
        self._inst_reg.update_state(instance_id, InstanceState.STOPPED)
        self._inst_reg.remove(instance_id)
        # Phase 4: Heartbeat 중단 (정상 종료 트리거)
        remaining = self._inst_reg.list_all()
        if not remaining:
            self._heartbeat.stop()
        else:
            self._write_state()
        return {"instance_id": instance_id, "state": InstanceState.STOPPED.value}

    def _write_state(self, *, ready: bool | None = None, last_error: str | None = None) -> None:
        ts = now_timestamps()
        instances = self._inst_reg.list_all()
        hot = [i for i in instances if i.state == InstanceState.HOT]
        _, pid_alive = self._check_pid()
        _ready = pid_alive if ready is None else ready
        self._state_file.write({
            "protocol": "ameva-component-status/1",
            "component_id": self.COMPONENT_ID,
            "component_type": self.COMPONENT_TYPE,
            "version": self._get_version(),
            "ready": _ready, "degraded": not _ready, **ts,
            "active_models": [i.model_id for i in hot],
            "last_error": last_error,
        })

    # ------------------------------------------------------------------
    # 13. transcribe (AMEVA Component Protocol v1 Orchestrator Bridge)
    # ------------------------------------------------------------------

    async def transcribe(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Executes STT transcription conforming to AMEVA Component Protocol v1.
        Dispatches to WhisperEngine asynchronously with strict contract validation.
        """
        import asyncio
        from termux_stt.engine.base import EngineConfig
        from termux_stt.engine.whisper_engine import WhisperEngine

        audio_path = request.get("audio_path")
        if not audio_path:
            return {
                "ok": False,
                "error": {
                    "code": "AUDIO_EMPTY",
                    "message": "audio_path is required for transcription",
                    "operation": "transcribe",
                    "retryable": False,
                }
            }

        audio_file = Path(audio_path)
        if not audio_file.exists():
            return {
                "ok": False,
                "error": {
                    "code": "AUDIO_NOT_FOUND",
                    "message": f"Audio file '{audio_path}' does not exist",
                    "operation": "transcribe",
                    "retryable": False,
                }
            }

        model_name = request.get("model_id") or request.get("model") or "base"
        language = request.get("language") or request.get("lang") or "ko"
        device = request.get("device") or "auto"
        threads = request.get("threads")

        config = EngineConfig(
            engine="whisper",
            model=model_name,
            lang=language,
            device=device,
            threads=threads,
        )

        def _run_transcribe() -> dict[str, Any]:
            engine = WhisperEngine(config)
            res = engine.transcribe(str(audio_file))
            text = (res.text or "").strip()
            if not text:
                return {
                    "ok": True,
                    "text": "",
                    "reason": "silence_detected",
                    "final": True,
                    "language": res.language or language,
                }
            return {
                "ok": True,
                "text": text,
                "final": True,
                "language": res.language or language,
                "segments": [
                    {"start": s.start, "end": s.end, "text": s.text}
                    for s in (res.segments or [])
                ],
            }

        try:
            return await asyncio.to_thread(_run_transcribe)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception("STTControl.transcribe error: %s", exc)
            return {
                "ok": False,
                "error": {
                    "code": getattr(exc, "code", "TRANSCRIPTION_FAILED"),
                    "message": str(exc),
                    "operation": "transcribe",
                    "retryable": False,
                }
            }

