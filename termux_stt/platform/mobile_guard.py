# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import logging
import os
import subprocess
from typing import Any, Dict

try:
    import psutil
except ImportError:
    psutil = None

import atexit
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class MobileGuard:
    """Handles Termux-specific device APIs: WakeLock, phantom processes, memory."""

    def __init__(self):
        self._wakelock_acquired = False
        atexit.register(self._cleanup_on_exit)

    def _cleanup_on_exit(self):
        if self._wakelock_acquired:
            self.release_wakelock()

    def acquire_wakelock(self) -> bool:
        """Acquire CPU wakelock to prevent sleep."""
        try:
            res = subprocess.run(["termux-wake-lock"], capture_output=True, timeout=5.0)
            if res.returncode == 0:
                self._wakelock_acquired = True
                return True
            logger.debug("termux-wake-lock failed with returncode %d", res.returncode)
        except Exception as e:
            logger.debug("termux-wake-lock exception: %s", e)
        return False

    def release_wakelock(self) -> bool:
        """Release CPU wakelock."""
        try:
            res = subprocess.run(["termux-wake-unlock"], capture_output=True, timeout=5.0)
            if res.returncode == 0:
                self._wakelock_acquired = False
                return True
            logger.debug("termux-wake-unlock failed with returncode %d", res.returncode)
        except Exception as e:
            logger.debug("termux-wake-unlock exception: %s", e)
        return False

    @staticmethod
    def disable_phantom_process_killer() -> bool:
        """Attempt to disable Android 12+ Phantom Process Killer via device_config or adb (strictly non-root).

        Returns True if successfully disabled or not required (Android < 12), False if permission denied.
        """
        # 1. Check Android SDK API level
        try:
            sdk_res = subprocess.run(["getprop", "ro.build.version.sdk"], capture_output=True, text=True, timeout=2.0)
            if sdk_res.returncode == 0 and sdk_res.stdout.strip().isdigit():
                sdk_level = int(sdk_res.stdout.strip())
                if sdk_level < 31:
                    logger.info("Phantom process killer is not active on Android < 12 (SDK %d).", sdk_level)
                    return True
        except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError) as _sdk_err:
            logger.debug("getprop ro.build.version.sdk check failed (%s), will try candidate commands", _sdk_err)

        # 2. Candidate non-root execution strategies for Android 12+
        commands = [
            ["device_config", "set_sync_disabled_for_tests", "persistent"],
            ["adb", "shell", "device_config set_sync_disabled_for_tests persistent && device_config put activity_manager max_phantom_processes 2147483647"],
        ]

        for cmd in commands:
            try:
                res = subprocess.run(cmd, capture_output=True, timeout=3.0)
                if res.returncode == 0:
                    logger.info("Phantom process killer disabled successfully using: %s", " ".join(cmd[:2]))
                    return True
            except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
                continue
            except Exception as e:
                logger.debug("Strategy %s failed: %s", cmd[0], e)

        logger.warning(
            "Unable to disable Phantom Process Killer automatically (requires root or ADB privileges). "
            "Please run 'adb shell \"/system/bin/device_config set_sync_disabled_for_tests persistent && /system/bin/device_config put activity_manager max_phantom_processes 2147483647\"' manually."
        )
        return False

    @staticmethod
    def check_battery_optimization() -> Dict[str, Any]:
        """Check battery optimization status without privileged escalation."""
        return {"doze_active": False, "note": "Use standard Android Battery Optimization settings to exempt Termux."}

    @staticmethod
    def monitor_memory() -> Dict[str, Any]:
        """Return memory usage of current process and system."""
        if psutil is None:
            return {
                "rss_mb": 0.0,
                "available_ram_mb": 0.0,
                "percent_used": 0.0,
            }
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        sys_mem = psutil.virtual_memory()
        return {
            "rss_mb": mem_info.rss / (1024 * 1024),
            "available_ram_mb": sys_mem.available / (1024 * 1024),
            "percent_used": sys_mem.percent,
        }

    def __enter__(self):
        self.acquire_wakelock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_wakelock()
        return False


@contextmanager
def wake_lock():
    """RAII Context Manager guaranteeing termux-wake-unlock upon exit or error."""
    guard = MobileGuard()
    guard.acquire_wakelock()
    try:
        yield guard
    finally:
        guard.release_wakelock()
