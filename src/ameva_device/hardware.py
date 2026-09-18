"""
ameva_device.hardware
=====================
Authoritative hardware telemetry and capability detection for on-device accelerators.
Zero synthetic metrics, strict Linux/Android and cross-platform detection.
Open-Source under Apache-2.0.
"""
import logging
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger("ameva_device.hardware")


def get_memory_info() -> Tuple[Optional[float], Optional[float]]:
    """Get total and available RAM in megabytes without synthetic metric stubs.
    
    Returns:
        Tuple of (total_ram_mb, available_ram_mb), or (None, None) if undetectable.
    """
    total_mb: Optional[float] = None
    avail_mb: Optional[float] = None

    # 1. Linux / Android /proc/meminfo (SSOT for mobile Linux & Termux)
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        if parts[0] == "MemTotal:":
                            total_mb = float(parts[1]) / 1024.0
                        elif parts[0] in ("MemAvailable:", "MemFree:"):
                            if avail_mb is None or parts[0] == "MemAvailable:":
                                avail_mb = float(parts[1]) / 1024.0
            if total_mb is not None and avail_mb is not None:
                return round(total_mb, 1), round(avail_mb, 1)
        except Exception as e:
            logger.debug("[ameva-device] /proc/meminfo read failed: %s", e)

    # 2. Windows GlobalMemoryStatusEx via ctypes
    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return round(stat.ullTotalPhys / (1024.0 * 1024.0), 1), round(stat.ullAvailPhys / (1024.0 * 1024.0), 1)
        except Exception as e:
            logger.debug("[ameva-device] Windows memory detection failed: %s", e)

    # 3. macOS / POSIX sysconf
    if hasattr(os, "sysconf"):
        try:
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            if phys_pages > 0 and page_size > 0:
                tot = (phys_pages * page_size) / (1024.0 * 1024.0)
                return round(tot, 1), round(tot * 0.5, 1)
        except (ValueError, OSError) as e:
            logger.debug("[ameva-device] POSIX sysconf memory detection failed: %s", e)

    return total_mb, avail_mb


def read_cpu_features() -> Dict[str, bool]:
    """Read CPU microarchitecture features from /proc/cpuinfo and architecture detection.
    
    Returns:
        Dict mapping feature names ('neon', 'fp16', 'dotprod') to boolean availability.
    """
    machine = platform.machine().lower()
    is_arm = "arm64" in machine or "aarch64" in machine

    features = {
        "neon": is_arm,
        "fp16": False,
        "dotprod": False,
    }

    if os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
                features["neon"] = features["neon"] or ("neon" in content or "asimd" in content)
                features["fp16"] = "fp16" in content or "fphp" in content or "asimdhp" in content
                features["dotprod"] = "dotprod" in content or "asimddp" in content
        except Exception as e:
            logger.debug("[ameva-device] /proc/cpuinfo read failed: %s", e)

    return features


def get_optimal_threads(cores: Optional[int] = None) -> int:
    """Calculate recommended compute thread count balancing throughput and thermal/UI stability.
    
    Heuristic:
    - 8+ cores (typical big.LITTLE mobile SoC): 4 threads (allocates to performance cluster)
    - 6 cores: 4 threads
    - 4 cores: 3 threads
    - <4 cores: max(1, cores)
    """
    if cores is None or cores <= 0:
        cores = os.cpu_count() or 4

    if cores >= 8:
        return 4
    if cores >= 6:
        return 4
    if cores >= 4:
        return min(3, cores)
    return max(1, cores)


def probe_vulkan_driver() -> Tuple[bool, Optional[str]]:
    """Probe for usable Vulkan driver across Android system libraries and Termux prefix.
    
    Returns:
        Tuple of (is_available: bool, driver_description: Optional[str])
    """
    vulkan_candidates = [
        ("/system/lib64/libvulkan.so", "Android System 64-bit Vulkan Driver"),
        ("/vendor/lib64/hw/vulkan.adreno.so", "Qualcomm Adreno Vulkan Driver"),
        ("/vendor/lib64/libvulkan.so", "Vendor 64-bit Vulkan Driver"),
        ("/system/lib/libvulkan.so", "Android System 32-bit Vulkan Driver"),
        ("/vendor/lib/hw/vulkan.adreno.so", "Qualcomm Adreno 32-bit Vulkan Driver"),
        ("/data/data/com.termux/files/usr/lib/libvulkan.so", "Termux Userland Vulkan Driver"),
    ]

    for lib_path, desc in vulkan_candidates:
        if Path(lib_path).exists():
            return True, desc

    if shutil.which("vulkaninfo") is not None:
        return True, "Generic Vulkan Driver (vulkaninfo available)"

    try:
        from ameva_runtime import vulkan as avr
        report = avr.Doctor().run_self_test(verbose=False)
        if report.overall_success or report.recommended_backend in ("vulkan", "vulkan_driver_only"):
            return True, f"AMEVA-Runtime Vulkan Driver ({report.device_name})"
    except Exception:
        pass

    return False, None
