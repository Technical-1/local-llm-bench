"""Find system executables without trusting the current directory.

Running a bare command name on Windows can resolve to a file in the current
directory before PATH, and ``shutil.which`` behaves the same way there. A
benchmark run from a downloads folder must not execute a planted
``powershell.exe`` or ``nvidia-smi.exe``, so every external command is
resolved to an absolute path here first.
"""

from __future__ import annotations

import os


def _is_exe(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def find_exe(name: str, known: tuple[str, ...] = (), search_path: bool = True) -> str | None:
    """Absolute path to ``name``: a known install location first, then PATH.

    PATH entries that are relative, empty, or the current directory are
    skipped, so the result never comes from wherever the user happens to be.
    """
    for candidate in known:
        if candidate and _is_exe(candidate):
            return candidate
    if not search_path:
        return None
    cwd = os.path.realpath(os.getcwd())
    if os.name == "nt":
        exts = [e for e in os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(";") if e]
        names = [name] if os.path.splitext(name)[1] else [name + e for e in exts]
    else:
        names = [name]
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry or not os.path.isabs(entry) or os.path.realpath(entry) == cwd:
            continue
        for n in names:
            path = os.path.join(entry, n)
            if _is_exe(path):
                return path
    return None


def windows_dir(*parts: str) -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), *parts)
