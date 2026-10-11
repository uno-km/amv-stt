# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from unittest.mock import MagicMock, patch

from termux_stt.platform.mobile_guard import MobileGuard, wake_lock


def test_mobile_guard_structure():
    assert isinstance(MobileGuard.disable_phantom_process_killer(), bool)
    battery_info = MobileGuard.check_battery_optimization()
    assert "doze_active" in battery_info
    mem_info = MobileGuard.monitor_memory()
    assert "rss_mb" in mem_info
    assert "available_ram_mb" in mem_info


def test_disable_phantom_process_killer_android_below_12():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="30\n")
        assert MobileGuard.disable_phantom_process_killer() is True


def test_disable_phantom_process_killer_android_12_nonroot_success():
    def mock_run_side_effect(cmd, **kwargs):
        if cmd[0] == "getprop":
            return MagicMock(returncode=0, stdout="33\n")
        if cmd[0] == "device_config":
            return MagicMock(returncode=0, stdout="")
        return MagicMock(returncode=1)

    with patch("subprocess.run", side_effect=mock_run_side_effect):
        assert MobileGuard.disable_phantom_process_killer() is True


def test_disable_phantom_process_killer_all_fail():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError()
        assert MobileGuard.disable_phantom_process_killer() is False


def test_wake_lock_context_manager():
    with wake_lock() as guard:
        assert guard is not None
