"""Executable lookup never resolves to the current directory."""

import os

from llm_bench._exe import find_exe


def _make_exe(path):
    path.write_text("#!/bin/sh\n")
    path.chmod(0o755)
    return path


def test_known_location_wins(tmp_path):
    exe = _make_exe(tmp_path / "tool")
    assert find_exe("tool", known=(str(exe),), search_path=False) == str(exe)


def test_found_on_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = _make_exe(bin_dir / ("tool.exe" if os.name == "nt" else "tool"))
    monkeypatch.setenv("PATH", str(bin_dir))
    assert find_exe("tool") == str(exe)


def test_current_directory_is_never_searched(tmp_path, monkeypatch):
    _make_exe(tmp_path / ("tool.exe" if os.name == "nt" else "tool"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", str(tmp_path)]))
    assert find_exe("tool") is None


def test_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    assert find_exe("definitely-not-installed") is None
