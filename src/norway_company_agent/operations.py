from __future__ import annotations

import math
import sys

try:
    import resource  # type: ignore[import-not-found]
except ImportError:  # Windows does not provide the Unix ``resource`` module.
    resource = None  # type: ignore[assignment]
from collections import Counter
from typing import Iterable


def percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between zero and one")
    index = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def latency_summary(values: Iterable[float]) -> dict[str, float | int | None]:
    measured = list(values)
    return {
        "n": len(measured),
        "p50_ms": round(percentile(measured, 0.50), 3) if measured else None,
        "p95_ms": round(percentile(measured, 0.95), 3) if measured else None,
        "max_ms": round(max(measured), 3) if measured else None,
    }


def domain_request_summary(counts: Counter[str]) -> dict[str, float | int | None]:
    values = list(counts.values())
    return {
        "domains": len(values),
        "p50_requests": percentile(values, 0.50),
        "p95_requests": percentile(values, 0.95),
        "max_requests": max(values) if values else None,
    }


def peak_rss_bytes() -> int:
    """Return peak resident memory in bytes on Unix and Windows."""
    if resource is not None:
        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes; Linux and most BSD-derived CI images report KiB.
        return int(value if sys.platform == "darwin" else value * 1024)

    if sys.platform == "win32":
        # Windows equivalent of ru_maxrss, without adding a third-party dependency.
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        process = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            process, ctypes.byref(counters), counters.cb
        )
        if not ok:
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)

    raise RuntimeError("Peak RSS measurement is unsupported on this platform")
