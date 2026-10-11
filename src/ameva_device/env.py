# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
ameva_device.env
================
Authoritative on-device environment diagnostics for Android Termux & Linux environments.
Open-Source under Apache-2.0.
"""
import os
from pathlib import Path


def is_termux() -> bool:
    """Authoritative detection for Android Termux environment."""
    if os.environ.get("TERMUX_VERSION") or os.environ.get("TERMUX_APP_PID"):
        return True
    prefix = os.environ.get("PREFIX", "")
    if "com.termux" in prefix:
        return True
    return Path("/data/data/com.termux").is_dir()


def is_android() -> bool:
    """Check whether running on Android.
    
    Within the Termux on-device ecosystem, running in Termux mathematically
    implies execution on the Android platform.
    """
    return is_termux()


def is_proot() -> bool:
    """Check if execution is running inside a PRoot container."""
    if os.environ.get("PROOT_TMP_DIR") or os.environ.get("PROOT"):
        return True
    try:
        mountinfo = Path("/proc/1/mountinfo")
        if mountinfo.exists():
            content = mountinfo.read_text(encoding="utf-8", errors="ignore")
            if "proot" in content.lower():
                return True
    except OSError:
        pass
    return False
