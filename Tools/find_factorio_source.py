#!/usr/bin/env python3
"""Find the original macOS Factorio game source on a Windows build host.

Searches known companion preferences first, then bounded local directories.
It does NOT read or modify FactorioData, unpack an IPA, or use shell commands.
Run directly on Windows:
    python F:/FactoriOS/Tools/find_factorio_source.py
    python F:/FactoriOS/Tools/find_factorio_source.py --root F:/ --root D:/
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import struct
import time

SKIP_DIRS = {
    ".git", ".svn", "FactorioData", "GameData", "node_modules",
    "__pycache__", ".venv", "venv", "ModuleCache", "ShaderCache",
    "$RECYCLE.BIN", "System Volume Information", "WindowsApps",
    "AppData", "Program Files", "Program Files (x86)",
    "OneDriveTemp", ".cache", "Library", "Objects",
}
ARCHIVE_EXT = {".dmg", ".zip", ".7z"}
MACHO_ARM64 = 0x0100000C
MH_EXECUTE = 2


def preferences_candidates() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    if not str(local) or str(local) == ".":
        return []
    return [
        local / "FactoriOS" / "Companion" / "settings.json",
        local / "FactorioPad" / "Companion" / "settings.json",
        local / "FactoriOS" / "settings.json",
    ]


def candidates_in_json(data: object) -> list[str]:
    found: list[str] = []
    if isinstance(data, str):
        val = data.strip().strip('"')
        if any(token in val.lower() for token in (".dmg", ".app", "factorio_mac_", "factorio.app")):
            found.append(val)
    elif isinstance(data, list):
        for obj in data:
            found.extend(candidates_in_json(obj))
    elif isinstance(data, dict):
        for obj in data.values():
            found.extend(candidates_in_json(obj))
    return found


def format_hit(path: Path) -> str | None:
    lower = str(path).lower()
    name = path.name.lower()
    if path.suffix.lower() in ARCHIVE_EXT and "factorio" in lower:
        return "archive"
    if name in {"factorio", "factorio.exe"} and (
        name == "factorio" or "factorio.app" in lower
    ):
        if name == "factorio.exe":
            return None
        try:
            with path.open("rb") as f:
                header = f.read(32)
            if len(header) >= 16:
                magic, cpu = struct.unpack_from("<II", header, 0)
                filetype = struct.unpack_from("<I", header, 12)[0]
                if magic == 0xFEEDFACF and cpu == MACHO_ARM64 and filetype == MH_EXECUTE:
                    return "original arm64 Mach-O executable"
                if header[:4] in (bytes.fromhex("cafebabe"), bytes.fromhex("cafebabf")):
                    return "fat Mach-O candidate (verify arm64 slice)"
        except OSError:
            pass
    return None


def default_roots() -> list[Path]:
    roots = [Path("F:/"), Path("D:/"), Path.home()]
    return [root for root in roots if root.is_dir()]


def scan(roots: list[Path], max_dirs: int, max_seconds: int, max_hits: int) -> None:
    start = time.monotonic()
    visited = 0
    hits: set[str] = set()
    stack = list(reversed(roots))
    while stack and visited < max_dirs and time.monotonic() - start < max_seconds and len(hits) < max_hits:
        folder = stack.pop()
        try:
            with os.scandir(folder) as it:
                dirs: list[Path] = []
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        p = Path(entry.path)
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name in SKIP_DIRS or entry.name.startswith("$"):
                                continue
                            dirs.append(p)
                        elif entry.is_file(follow_symlinks=False):
                            kind = format_hit(p)
                            if kind and str(p) not in hits:
                                hits.add(str(p))
                                size = entry.stat(follow_symlinks=False).st_size
                                print(f"FOUND [{kind}] {p} ({size:,} bytes)")
                                if len(hits) >= max_hits:
                                    break
                    except (OSError, PermissionError):
                        continue
                stack.extend(reversed(dirs))
            visited += 1
        except (OSError, PermissionError):
            continue
        if visited % 5000 == 0:
            print(f"Scanned {visited:,} directories; found {len(hits)} candidate(s)")
    duration = int(time.monotonic() - start)
    remaining = len(stack)
    print(f"SCAN COMPLETE searched={visited:,} directories duration={duration}s hits={len(hits)} pending={remaining}")
    if not hits:
        print("No local original found within search limits. Do not substitute the already patched FactorioGuest.")
        print("Next: obtain the original macOS 2.1.24 DMG from the authorized game source or inspect previously cached original app files.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path, default=None)
    parser.add_argument("--max-dirs", type=int, default=25000)
    parser.add_argument("--max-seconds", type=int, default=90)
    parser.add_argument("--max-hits", type=int, default=30)
    options = parser.parse_args()
    print("Companion preferences:")
    for settings in preferences_candidates():
        if not settings.is_file():
            continue
        print(f"SETTINGS {settings}")
        try:
            values = candidates_in_json(json.loads(settings.read_text(encoding="utf-8-sig")))
            for value in sorted(set(values)):
                print(f"  remembered source: {value}")
                print(f"  exists: {Path(value).exists()}")
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            print(f"  cannot read settings: {error}")
    roots = options.root or default_roots()
    print("Search roots: " + ", ".join(map(str, roots)))
    scan(roots, options.max_dirs, options.max_seconds, options.max_hits)


if __name__ == "__main__":
    main()
