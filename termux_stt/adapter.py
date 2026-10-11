# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
termux_stt.adapter
===================
AMEVA Component Protocol v1 — Orchestrator Adapter (v0.8.1 호환)

P0-2: infer() fallback yield _not_supported → raise OperationNotSupported
P0-3: 성공 결과의 text 필드 엄격 검증 (result.get("text","") 제거)
P0-4: except Exception → 오류 유형별 retryable 분류, 원본 코드 보존
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from ameva_component.adapter_base import BaseOrchestratorAdapter
from ameva_component.exceptions import (
    ComponentError,
    OperationNotSupported,
    redact_details,
    redact_text,
)
from termux_stt.control.component import STTControl


class STTOrchestratorAdapter(BaseOrchestratorAdapter):
    """STT (Speech-to-Text) Orchestrator Adapter.

    음성 파일 변환은 Whisper.cpp를 통해 파일 기반으로 수행됩니다.
    infer(): 오디오 파일 경로를 받아 transcript를 반환합니다.
    partial / silence / decode 실패를 구분하여 반환합니다.
    """

    COMPONENT_ID = "termux-stt"

    # P0-4: retryable 분류 기준
    _RETRYABLE_CODES: frozenset[str] = frozenset({
        "REMOTE_TIMEOUT",
        "MODEL_BUSY",
        "TEMPORARY_RESOURCE_UNAVAILABLE",
    })
    _NON_RETRYABLE_CODES: frozenset[str] = frozenset({
        "AUDIO_DECODE_FAILED",
        "AUDIO_PATH_FORBIDDEN",
        "MODEL_NOT_FOUND",
        "HASH_MISMATCH",
        "AUDIO_FORMAT_UNSUPPORTED",
        "AUDIO_CORRUPT",
    })

    def __init__(self, control: STTControl | None = None) -> None:
        self._control = control or STTControl()

    async def infer(self, request: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """STT inference: audio_path 기반 transcription.

        request 키:
            audio_path (str): 음성 파일 경로 (필수)
            model_id (str): 사용할 모델 ID (선택)
            language (str): 언어 코드 (선택)

        반환 프레임:
            {"type": "transcript", "text": str, "final": bool, "language": str | None}
            {"type": "silence", "reason": "silence_detected", "final": bool}
            {"type": "error", "ok": False, "error": {...}}
        """
        audio_path = request.get("audio_path")
        if not audio_path:
            yield {
                "type": "error",
                "ok": False,
                "error": {
                    "code": "AUDIO_EMPTY",
                    "message": "audio_path is required for STT infer",
                    "operation": "infer",
                    "component_id": self.COMPONENT_ID,
                    "retryable": False,
                },
            }
            return

        if not hasattr(self._control, "transcribe"):
            # P0-2: yield not_supported → raise
            raise OperationNotSupported(operation="infer.transcribe", component_id=self.COMPONENT_ID)

        try:
            result = await self._control.transcribe(request)

            # P0-3: 성공 결과 엄격 검증
            if not isinstance(result, dict):
                raise ValueError(
                    f"transcribe() must return dict, got {type(result).__name__}"
                )
            if result.get("ok") is not True:
                # HIGH 1: ComponentControl 성공 결과는 ok=True 필수
                err_payload = result.get("error") if isinstance(result.get("error"), dict) else {}
                yield {
                    "type": "error",
                    "ok": False,
                    "error": {
                        "code": err_payload.get("code", "ADAPTER_RESULT_NOT_SUCCESS"),
                        "message": err_payload.get("message", "transcribe() did not return ok=True"),
                        "operation": "infer",
                        "component_id": self.COMPONENT_ID,
                        "retryable": False,
                        "details": {"result_keys": sorted(result.keys())},
                    },
                }
                return

            if "text" not in result:
                raise ValueError("transcribe() result missing required field 'text'")

            text = result["text"]
            if text is None:
                raise ValueError("transcribe() returned text=None — use empty string with reason='silence_detected' for silence")
            if not isinstance(text, str):
                raise TypeError(f"transcribe() text must be str, got {type(text).__name__}")

            # 정상 Silence 구분: text가 빈 문자열이면 reason 필드로 명시
            if text == "" and result.get("reason") == "silence_detected":
                yield {
                    "type": "silence",
                    "text": "",
                    "reason": "silence_detected",
                    "final": True,
                    "language": result.get("language"),
                    "ok": True,
                }
                return

            if text == "" and "reason" not in result:
                raise ValueError(
                    "transcribe() returned empty text without reason='silence_detected'. "
                    "Use reason='silence_detected' for actual silence."
                )

            final = result.get("final", True)

            yield {
                "type": "transcript",
                "text": text,
                "final": bool(final),
                "language": result.get("language"),
                "fallback_used": result.get("fallback_used", False),
                "ok": True,
            }

        except ComponentError as component_err:
            # HIGH 1: ComponentError public_message와 redact_details로 외부 노출 보안 격리
            import logging
            logging.getLogger(__name__).exception(
                "STT component operation failed",
                extra={
                    "component_id": self.COMPONENT_ID,
                    "operation": "infer",
                    "code": getattr(component_err, "code", "COMPONENT_ERROR"),
                },
            )
            if hasattr(component_err, "to_public_dict"):
                err_dict = component_err.to_public_dict()
            else:
                err_dict = {
                    "code": getattr(component_err, "code", "COMPONENT_ERROR"),
                    "message": redact_text(getattr(component_err, "public_message", "Component operation failed")),
                    "retryable": getattr(component_err, "retryable", False),
                    "details": redact_details(getattr(component_err, "details", {})),
                }
            yield {
                "type": "error",
                "ok": False,
                "error": {
                    **err_dict,
                    "operation": "infer",
                    "component_id": self.COMPONENT_ID,
                    "retryable": self._classify_retryable(
                        err_dict.get("code", ""), default=err_dict.get("retryable", False)
                    ),
                },
            }

        except (ValueError, TypeError) as contract_err:
            # P0-3/4 & HIGH 1: 계약 위반 (str(contract_err) 직접 노출 금지, 내부 로그 격리)
            import logging
            logging.getLogger(__name__).exception("STT contract validation error during infer: %s", contract_err)
            yield {
                "type": "error",
                "ok": False,
                "error": {
                    "code": "ADAPTER_CONTRACT_ERROR",
                    "message": "Adapter contract validation failed",
                    "operation": "infer",
                    "component_id": self.COMPONENT_ID,
                    "retryable": False,
                    "details": {
                        "cause_type": type(contract_err).__name__,
                        "operation": "infer",
                    },
                },
            }

        except Exception as unexpected_err:
            # HIGH 2: 보안을 위해 내부 경로/민감정보가 담길 수 있는 str(exc) 외부 노출 방지
            import logging
            logging.getLogger(__name__).exception("STT adapter unexpected error during infer: %s", unexpected_err)
            code = getattr(unexpected_err, "code", "ADAPTER_INTERNAL_ERROR")
            yield {
                "type": "error",
                "ok": False,
                "error": {
                    "code": code if isinstance(code, str) else "ADAPTER_INTERNAL_ERROR",
                    "message": "Unexpected adapter failure",
                    "operation": "infer",
                    "component_id": self.COMPONENT_ID,
                    "retryable": False,
                    "details": {
                        "cause_type": type(unexpected_err).__name__,
                        "operation": "infer",
                    },
                },
            }

    def _classify_retryable(self, code: str, *, default: bool = False) -> bool:
        """P0-4: 오류 코드 기반 retryable 분류."""
        if code in self._RETRYABLE_CODES:
            return True
        if code in self._NON_RETRYABLE_CODES:
            return False
        return default


def create_adapter() -> STTOrchestratorAdapter:
    """Entry Point Factory."""
    return STTOrchestratorAdapter()
