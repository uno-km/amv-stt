# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
termux_stt.control.status
AMEVA Component Protocol v1 — STT 상태 파일 Writer + Heartbeat
"""
from __future__ import annotations
from typing import Any
from ameva_component.heartbeat import HeartbeatWriter


class STTStatusWriter(HeartbeatWriter):
    """STTControl 상태를 10초마다 상태 파일에 원자적으로 기록합니다."""

    def __init__(self, control: Any) -> None:
        super().__init__(control, name="stt")
