# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Result export module for termux-stt.
"""
from .result import DiarizedResult, Segment, TranscriptResult

__all__ = ['TranscriptResult', 'Segment', 'DiarizedResult']
