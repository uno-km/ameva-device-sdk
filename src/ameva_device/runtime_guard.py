# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Runtime guard for GPU-requiring features.

Every termux-* package runs on the CPU by itself. GPU execution is provided by
``ameva-runtime`` (AMUDA). When a GPU run is requested and the runtime is missing
or too old, the process must stop with an explicit error that explains how to
install it. It must not continue on the CPU without telling the user.

Detection only checks that the runtime package is importable and at least the
requested version. It does not prove that a GPU device works; use
``ameva-run doctor`` for that.
"""

import importlib
import importlib.util
import re
import sys
from typing import Optional, Tuple

RUNTIME_REQUIRED_CODE = "AMU_ERR_RUNTIME_REQUIRED"
# Exit status used by command-line entry points (sysexits EX_UNAVAILABLE).
RUNTIME_REQUIRED_EXIT_CODE = 69
DEFAULT_MIN_VERSION = "2.0.0"
RUNTIME_PYPI_NAME = "ameva-runtime"
RUNTIME_NPM_NAME = "@ameva/runtime"
RUNTIME_RELEASES_URL = "https://github.com/uno-km/ameva-runtime-releases"


def parse_version(text: str) -> Tuple[int, ...]:
    """Return the leading numeric components of a version string, e.g. '2.8.1rc1' -> (2, 8, 1)."""
    parts = []
    for piece in str(text).strip().split("."):
        match = re.match(r"\d+", piece)
        if not match:
            break
        parts.append(int(match.group(0)))
    return tuple(parts)


def installed_runtime_version() -> Optional[str]:
    """Return the installed ameva-runtime version string, or None when it is not importable."""
    try:
        if importlib.util.find_spec("ameva_runtime") is None:
            return None
        module = importlib.import_module("ameva_runtime")
    except (ImportError, ValueError, AttributeError):
        return None
    version = getattr(module, "__version__", None)
    return str(version) if version else "unknown"


def runtime_required_message(component: str, feature: str, min_version: str,
                             found: Optional[str]) -> str:
    """Build the user-facing explanation. Plain ASCII so that every terminal renders it."""
    if found is None:
        state = "ameva-runtime is not installed."
    elif found == "unknown":
        state = "ameva-runtime is installed but its version could not be read (need >= %s)." % min_version
    else:
        state = "ameva-runtime %s is installed, but >= %s is required." % (found, min_version)
    return (
        "[{code}] {component}: '{feature}' needs the AMEVA GPU runtime.\n"
        "{state}\n"
        "Nothing was run, and no CPU fallback was used.\n"
        "\n"
        "What is AMUDA / ameva-runtime:\n"
        "  AMUDA is AMEVA's GPU compute layer for Android phones (Vulkan and OpenCL on\n"
        "  Adreno and Mali GPUs). It ships inside ameva-runtime and runs the model kernels\n"
        "  on the phone's GPU. Without it this tool can only run on the CPU.\n"
        "\n"
        "Install:\n"
        "  pip:   pip install \"{pypi}>={minv}\"\n"
        "  npm:   npm install -g {npm}\n"
        "  check: ameva-run doctor\n"
        "  Releases and documentation: {url}\n"
        "\n"
        "To run on the CPU instead, request it explicitly (for example --device cpu).\n"
    ).format(code=RUNTIME_REQUIRED_CODE, component=component, feature=feature, state=state,
             pypi=RUNTIME_PYPI_NAME, npm=RUNTIME_NPM_NAME, minv=min_version, url=RUNTIME_RELEASES_URL)


class AmevaRuntimeRequiredError(RuntimeError):
    """Raised when a GPU feature is requested and ameva-runtime is missing or too old."""

    code = RUNTIME_REQUIRED_CODE

    def __init__(self, component: str, feature: str, min_version: str, found: Optional[str]):
        self.component = component
        self.feature = feature
        self.min_version = min_version
        self.found = found
        super().__init__(runtime_required_message(component, feature, min_version, found))


def require_ameva_runtime(component: str, feature: str = "GPU execution",
                          min_version: str = DEFAULT_MIN_VERSION) -> str:
    """Return the installed runtime version, or raise AmevaRuntimeRequiredError.

    Call this at the start of every code path that was asked to use the GPU.
    """
    found = installed_runtime_version()
    if found is None:
        raise AmevaRuntimeRequiredError(component, feature, min_version, None)
    if found == "unknown" or parse_version(found) < parse_version(min_version):
        raise AmevaRuntimeRequiredError(component, feature, min_version, found)
    return found


def exit_if_runtime_missing(component: str, feature: str = "GPU execution",
                            min_version: str = DEFAULT_MIN_VERSION) -> str:
    """Command-line variant: print the explanation to stderr and exit with status 69."""
    try:
        return require_ameva_runtime(component, feature, min_version)
    except AmevaRuntimeRequiredError as err:
        sys.stderr.write(str(err))
        sys.stderr.flush()
        raise SystemExit(RUNTIME_REQUIRED_EXIT_CODE)
