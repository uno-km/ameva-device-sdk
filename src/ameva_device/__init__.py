"""
AMEVA Device SDK (ameva-device-sdk)
==================================
The Authoritative On-Device Systems Foundation for the AMEVA & uno-km Ecosystem.
Open-Source under Apache-2.0.
"""

from .env import is_android, is_proot, is_termux
from .hardware import (
    get_memory_info,
    get_optimal_threads,
    probe_vulkan_driver,
    read_cpu_features,
)
from .storage import (
    atomic_replace,
    check_disk_space,
    download_file_atomic,
    get_unified_model_search_dirs,
    verify_file_sha256,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Environment
    "is_termux",
    "is_android",
    "is_proot",
    # Hardware Telemetry
    "get_memory_info",
    "read_cpu_features",
    "get_optimal_threads",
    "probe_vulkan_driver",
    # Storage & Integrity
    "get_unified_model_search_dirs",
    "verify_file_sha256",
    "check_disk_space",
    "atomic_replace",
    "download_file_atomic",
]
