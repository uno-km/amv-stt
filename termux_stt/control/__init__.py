# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""termux_stt.control — AMEVA Component Protocol v1."""
from .component import STTControl
from .status import STTStatusWriter
__all__ = ["STTControl", "STTStatusWriter"]
