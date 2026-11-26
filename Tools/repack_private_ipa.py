#!/usr/bin/env python3
"""Replace only FactorioCompat in an existing private, unsigned FactoriOS IPA.

Does not read or modify the separate FactorioData folder. Keeps FactorioGuest
bit-for-bit unchanged. The resulting IPA must be signed by the sideload tool.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
import pathlib
import shutil
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIVATE_DIR = ROOT / "dist" / "private-duo-test-2.1.24"
BUILD = pathlib.Path(os.environ.get(
    "FACTORIOS_BUILD_DIR", r"F:\NXNative\Builds\FactoriOS-ios27"
))
COMPAT_SUFFIX = "/Frameworks/FactorioCompat.framework/FactorioCompat"
GUEST_SUFFIX = "/Frameworks/FactorioGuest.framework/FactorioGuest"


def hash_member(archive: zipfile.ZipFile, name: str) -> str:
    checksum = hashlib.sha256()
    with archive.open(name) as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ipa", type=pathlib.Path, default=PRIVATE_DIR / "FactorioPad.ipa")
    p.add_argument("--framework", type=pathlib.Path,
                   default=BUILD / "Product" / "FactorioCompat.framework" / "FactorioCompat")
    p.add_argument("--output", type=pathlib.Path,
                   default=PRIVATE_DIR / "FactorioPad-compat-fix.ipa")
    a = p.parse_args()

    if not a.ipa.is_file() or not a.framework.is_file():
        raise FileNotFoundError(f"Missing IPA or rebuilt compatibility framework: {a.ipa} / {a.framework}")
    if a.output.exists() or a.output.resolve() == a.ipa.resolve():
        raise FileExistsError(f"Refusing to overwrite existing file: {a.output}")
    a.output.parent.mkdir(parents=True, exist_ok=True)

    stage = None
    try:
        with zipfile.ZipFile(a.ipa) as original:
            if original.testzip() is not None:
                raise ValueError("Original IPA failed CRC validation")
            names = original.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Original IPA has duplicate entry names")
            compat = [n for n in names if n.startswith("Payload/") and n.endswith(COMPAT_SUFFIX)]
            guest = [n for n in names if n.startswith("Payload/") and n.endswith(GUEST_SUFFIX)]
            if len(compat) != 1 or len(guest) != 1:
                raise ValueError(f"Expected exactly one compatible framework and guest: {len(compat)}, {len(guest)}")
            if any("/_CodeSignature/" in n for n in names):
                raise ValueError("The source IPA appears signed. Repackage an unsigned IPA, then sign after replacing.")
            guest_before = hash_member(original, guest[0])

            fd, stage = tempfile.mkstemp(prefix="factorios-compat-", suffix=".ipa", dir=a.output.parent)
            os.close(fd)
            with zipfile.ZipFile(stage, "w", allowZip64=True) as patched:
                for entry in original.infolist():
                    new_entry = copy.copy(entry)  # preserves permissions and compression metadata
                    with patched.open(new_entry, "w", force_zip64=True) as dest:
                        if entry.filename == compat[0]:
                            with a.framework.open("rb") as source:
                                shutil.copyfileobj(source, dest, length=1024 * 1024)
                        else:
                            with original.open(entry) as source:
                                shutil.copyfileobj(source, dest, length=1024 * 1024)

            with zipfile.ZipFile(stage) as check:
                if check.testzip() is not None:
                    raise ValueError("Repacked IPA failed CRC validation")
                if check.namelist() != names:
                    raise ValueError("IPA entry list changed unexpectedly")
                if hash_member(check, guest[0]) != guest_before:
                    raise ValueError("FactorioGuest was modified during repack")
                changed = [name for name in names
                           if check.getinfo(name).CRC != original.getinfo(name).CRC
                           or check.getinfo(name).file_size != original.getinfo(name).file_size]
                if changed != compat:
                    raise ValueError(f"Unexpected modified IPA entries: {changed[:20]}")
                if not ((check.getinfo(compat[0]).external_attr >> 16) & 0o111):
                    raise ValueError("Compatibility framework lost executable permissions")

        os.rename(stage, a.output)  # fail rather than overwrite if output already exists
        stage = None
        print(f"Private unsigned IPA: {a.output}")
        print(f"Replaced entry: {compat[0]}")
        print(f"FactorioGuest unchanged SHA-256: {guest_before}")
        print("FactorioData was not accessed. Sign/install the IPA with the existing sideload workflow.")
        return 0
    finally:
        if stage and os.path.exists(stage):
            os.unlink(stage)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"REPACK ERROR: {error}", file=sys.stderr)
        sys.exit(1)
