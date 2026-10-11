# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
"""
Tests for the GPU runtime guard. The runtime is simulated through sys.modules and the
installed-version probe; no GPU and no real ameva-runtime are needed.
"""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import ameva_device as dev
from ameva_device import runtime_guard as rg


def _fake_runtime(monkeypatch, version):
    mod = types.ModuleType("ameva_runtime")
    if version is not None:
        mod.__version__ = version
    mod.__spec__ = __import__("importlib.machinery").machinery.ModuleSpec("ameva_runtime", None)
    monkeypatch.setitem(sys.modules, "ameva_runtime", mod)


def _no_runtime(monkeypatch):
    monkeypatch.setattr(rg.importlib.util, "find_spec", lambda name, *a, **k: None)
    monkeypatch.delitem(sys.modules, "ameva_runtime", raising=False)


def test_parse_version():
    assert rg.parse_version("2.8.1") == (2, 8, 1)
    assert rg.parse_version("2.8.1rc1") == (2, 8, 1)
    assert rg.parse_version("2.10.0") > rg.parse_version("2.9.9")
    assert rg.parse_version("garbage") == ()


def test_missing_runtime_raises_with_install_guidance(monkeypatch):
    _no_runtime(monkeypatch)
    with pytest.raises(dev.AmevaRuntimeRequiredError) as info:
        dev.require_ameva_runtime("termux-test", "GPU inference")
    text = str(info.value)
    assert info.value.code == "AMU_ERR_RUNTIME_REQUIRED"
    assert text.startswith("[AMU_ERR_RUNTIME_REQUIRED] termux-test:")
    assert "not installed" in text
    assert "no CPU fallback was used" in text
    assert "pip install \"ameva-runtime>=2.0.0\"" in text
    assert "npm install -g @ameva/runtime" in text
    assert "AMUDA" in text
    assert "https://github.com/uno-km/ameva-runtime-releases" in text
    assert "--device cpu" in text


def test_old_runtime_is_rejected(monkeypatch):
    _fake_runtime(monkeypatch, "1.9.0")
    with pytest.raises(dev.AmevaRuntimeRequiredError) as info:
        dev.require_ameva_runtime("termux-test", "GPU inference", min_version="2.0.0")
    assert info.value.found == "1.9.0"
    assert "1.9.0 is installed, but >= 2.0.0 is required" in str(info.value)


def test_unreadable_version_is_rejected_not_assumed(monkeypatch):
    _fake_runtime(monkeypatch, None)
    with pytest.raises(dev.AmevaRuntimeRequiredError) as info:
        dev.require_ameva_runtime("termux-test")
    assert info.value.found == "unknown"
    assert "version could not be read" in str(info.value)


def test_sufficient_runtime_passes(monkeypatch):
    _fake_runtime(monkeypatch, "2.8.1")
    assert dev.require_ameva_runtime("termux-test", min_version="2.8.0") == "2.8.1"
    assert dev.installed_runtime_version() == "2.8.1"


def test_exit_variant_prints_to_stderr_and_exits_69(monkeypatch, capsys):
    _no_runtime(monkeypatch)
    with pytest.raises(SystemExit) as exit_info:
        dev.exit_if_runtime_missing("termux-test", "GPU inference")
    assert exit_info.value.code == dev.RUNTIME_REQUIRED_EXIT_CODE == 69
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "AMU_ERR_RUNTIME_REQUIRED" in captured.err


def test_message_is_ascii():
    text = rg.runtime_required_message("c", "f", "2.0.0", None)
    text.encode("ascii")
