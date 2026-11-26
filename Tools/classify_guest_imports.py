#!/usr/bin/env python3
"""Classify FactoriOS's missing direct exports against ORIGINAL Mach-O bindings.

Reads only the original game executable from the user's 2.1.24 DMG and two
embedded binaries from an existing private IPA. Does not touch FactorioData.

python F:/FactoriOS/Tools/classify_guest_imports.py
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIVATE = (ROOT / "dist" /
    "private-duo-ios27-routing-20261126-163940-05bdf15")
SDK = Path(r"F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk")
SEVENZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
LLVM = Path(r"C:\Program Files\LLVM\bin")
LC_LOAD = {0x0c, 0x18, 0x1f, 0x23, 0x20}  # command flags stripped
MAC_EXEC = "Factorio/factorio.app/Contents/MacOS/factorio"


def invoke(*args: str) -> str:
    result = subprocess.run(list(map(str, args)), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, errors="replace")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {args[0]}\n"
                           + result.stderr[-1200:] + result.stdout[-600:])
    return result.stdout


def original_arm64(raw: bytes) -> bytes:
    if struct.unpack_from("<I", raw)[0] == 0xFEEDFACF:
        if struct.unpack_from("<I", raw, 4)[0] != 0x0100000C:
            raise ValueError("Original Mach-O is not arm64")
        return raw
    magic, count = struct.unpack_from(">II", raw)
    if magic not in (0xCAFEBABE, 0xCAFEBABF):
        raise ValueError("Original executable is not a supported Mach-O")
    wide = magic == 0xCAFEBABF
    step = 32 if wide else 20
    for idx in range(count):
        pos = 8 + idx * step
        if pos + step > len(raw):
            raise ValueError("Malformed fat Mach-O slice table")
        cpu = struct.unpack_from(">I", raw, pos)[0]
        if cpu != 0x0100000C:
            continue
        if wide:
            offset, size = struct.unpack_from(">QQ", raw, pos + 8)
        else:
            offset, size = struct.unpack_from(">II", raw, pos + 8)
        if not (0 <= offset < len(raw) and 0 < size <= len(raw)-offset):
            raise ValueError("Invalid arm64 slice bounds")
        return raw[offset:offset+size]
    raise ValueError("No arm64 slice in original executable")


def dylib_commands(raw: bytes) -> list[str]:
    if len(raw) < 32 or struct.unpack_from("<I", raw)[0] != 0xFEEDFACF:
        raise ValueError("Expected thin arm64 Mach-O")
    ncmds, sizeofcmds = struct.unpack_from("<II", raw, 16)
    off, end = 32, 32 + sizeofcmds
    names: list[str] = []
    for _ in range(ncmds):
        if off + 8 > min(end, len(raw)):
            raise ValueError("Malformed Mach-O load-command header")
        cmd, size = struct.unpack_from("<II", raw, off)
        if size < 8 or off + size > min(end, len(raw)):
            raise ValueError("Malformed Mach-O load-command size")
        if cmd & 0x7fffffff in LC_LOAD:
            name_offset = struct.unpack_from("<I", raw, off + 8)[0]
            if not 24 <= name_offset < size:
                raise ValueError("Malformed dylib name offset")
            value = raw[off+name_offset:off+size].split(b"\0", 1)[0].decode(
                "utf-8", "replace")
            names.append(value)
        off += size
    if off != end:
        raise ValueError("Malformed Mach-O load commands end")
    return names


def bind_rows(binary: Path, llvm: Path) -> list[dict]:
    records = []
    for flag in ("--bind", "--lazy-bind"):
        output = invoke(str(llvm / "llvm-objdump.exe"),
                        "--macho", flag, str(binary))
        for line in output.splitlines():
            columns = line.split()
            if len(columns) < 4:
                continue
            symbol = columns[-1]
            if not symbol.startswith("_"):
                continue
            address = next((part.lower() for part in columns
                            if re.fullmatch(r"0x[0-9a-fA-F]+", part)), None)
            records.append({
                "symbol": symbol,
                "address": address,
                "dylib": columns[-2],
                "kind": flag.lstrip("-"),
                "raw": line.strip(),
            })
    return records


def provider_library(imported: str) -> str:
    matched = re.search(r"([^/]+)\.framework/", imported)
    if matched:
        return matched.group(1)
    if "libSystem" in imported or "libm." in imported:
        return "libSystem"
    return imported


def sdk_candidates(sdk: Path, provider: str) -> list[Path]:
    if provider == "libSystem":
        return sorted((sdk / "usr" / "lib").glob("libSystem*.tbd")) + list(
            (sdk / "usr" / "lib").glob("libm*.tbd"))
    frameworks = sdk / "System" / "Library" / "Frameworks"
    direct = list((frameworks / (provider + ".framework")).rglob("*.tbd"))
    if provider == "CoreServices":
        for alternative in ("MobileCoreServices", "UniformTypeIdentifiers"):
            direct.extend((frameworks / (alternative + ".framework")).rglob("*.tbd"))
    return sorted(set(direct))


def tbd_names(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sdk_matches(symbol: str, paths: list[Path], cache: dict) -> list[str]:
    lookfor = symbol
    if symbol.startswith("_OBJC_CLASS_$_"):
        lookfor = symbol.split("$_", 1)[1]
    # A textual occurrence in an SDK tbd is only a CANDIDATE export:
    # the target/platform, reexports and runtime availability need verification.
    pattern = re.compile(r"(?<![\w.$])" + re.escape(lookfor) + r"(?![\w.$])")
    matches = []
    for p in paths:
        try:
            text = cache.setdefault(p, tbd_names(p))
            if pattern.search(text):
                matches.append(str(p))
        except OSError:
            pass
    return matches


def classify(ipa_path: Path, dmg: Path, sdk: Path,
             llvm: Path, sevenzip: Path, report: Path) -> None:
    if not ipa_path.is_file() or not dmg.is_file():
        raise FileNotFoundError(f"Missing input IPA or original DMG: {ipa_path}; {dmg}")
    with tempfile.TemporaryDirectory(prefix="factorios-ordinal-") as td:
        temp = Path(td)
        with zipfile.ZipFile(ipa_path) as archive:
            names = archive.namelist()
            matches = [n for n in names if n.startswith("Payload/")
                       and n.endswith("/Frameworks/FactorioGuest.framework/FactorioGuest")]
            if len(matches) != 1:
                raise RuntimeError("Expected exactly one packaged FactorioGuest binary")
            guest = temp / "guest"
            guest.write_bytes(archive.read(matches[0]))
        extraction = temp / "source"
        extraction.mkdir()
        invoke(str(sevenzip), "x", "-y", "-bd", "-bso0", "-bsp0",
               "-o" + str(extraction), str(dmg), MAC_EXEC)
        original_file = extraction / MAC_EXEC
        if not original_file.is_file():
            raise FileNotFoundError("DMG extraction did not produce original executable")
        original = temp / "original-arm64"
        original.write_bytes(original_arm64(original_file.read_bytes()))

        old_dylibs = dylib_commands(original.read_bytes())
        new_dylibs = dylib_commands(guest.read_bytes())
        if len(old_dylibs) != len(new_dylibs):
            raise RuntimeError("Patched guest changed library ordinals unexpectedly")
        mapping = [{
            "ordinal": i + 1, "original": old,
            "patched": new, "original_provider": provider_library(old),
        } for i, (old, new) in enumerate(zip(old_dylibs, new_dylibs))]

        original_bindings = bind_rows(original, llvm)
        patched_bindings = bind_rows(guest, llvm)
        # Match the same location and symbol. dyld bind data is unchanged by
        # header dependency routing, but verify rather than assume.
        old_at_address = defaultdict(list)
        old_by_symbol = defaultdict(list)
        for row in original_bindings:
            if row["address"]:
                old_at_address[(row["address"], row["symbol"])].append(row)
            old_by_symbol[row["symbol"]].append(row)

        missing_path = report.parent / "audit" / "missing-strong-compat-exports.txt"
        if not missing_path.is_file():
            raise FileNotFoundError(f"Saved 64-symbol audit list missing: {missing_path}")
        missing = sorted(set(x.strip() for x in missing_path.read_text(
            encoding="utf-8").splitlines() if x.strip()))
        groups = defaultdict(list)
        tbd_cache = {}
        for symbol in missing:
            imported = [r for r in patched_bindings if r["symbol"] == symbol]
            originals = []
            for imported_row in imported:
                aligned = old_at_address.get((imported_row["address"], symbol), [])
                originals.extend(aligned)
            # Symbol-only match is used only if unambiguous; otherwise mark unknown.
            if not originals and len(old_by_symbol[symbol]) == 1:
                originals = old_by_symbol[symbol]
            providers = sorted(set(x["dylib"] for x in originals)) or ["UNKNOWN"]
            group = ", ".join(providers)
            sdk_hits = []
            for p in providers:
                sdk_hits.extend(sdk_matches(symbol, sdk_candidates(sdk, provider_library(p)), tbd_cache))
            groups[group].append({
                "symbol": symbol,
                "original_bind_rows": [x["raw"] for x in originals[:8]],
                "patched_bind_rows": [x["raw"] for x in imported[:8]],
                "sdk_tbd_candidates": sorted(set(sdk_hits)),
                "conclusion": "SDK candidate; verify correct iOS target/runtime" if sdk_hits
                              else "No matching public SDK stub found; requires further implementation/proof",
            })
        ipa_digest = hashlib.sha256()
        with ipa_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                ipa_digest.update(chunk)
        payload = {
            "ipa": str(ipa_path),
            "ipa_sha256": ipa_digest.hexdigest(),
            "original_dmg": str(dmg),
            "library_ordinals": mapping,
            "missing_direct_export_count": len(missing),
            "grouped_by_original_bind_provider": dict(sorted(groups.items())),
            "note": "A .tbd text hit is not runtime proof. UNKNOWN group must be audited manually.",
        }
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Existing IPA: {ipa_path}")
        print(f"64-symbol report: {report}")
        print(f"Original library ordinals: {len(mapping)}")
        print(f"Missing direct FactorioCompat symbols: {len(missing)}")
        for group, items in sorted(groups.items(), key=lambda pair: -len(pair[1])):
            hit = sum(bool(x["sdk_tbd_candidates"]) for x in items)
            print(f"  {group}: {len(items)} symbols, {hit} public-SDK-stub candidates")
            for item in items[:6]:
                print(f"      {item['symbol']}")
            if len(items) > 6:
                print(f"      ... {len(items)-6} more in JSON")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=Path, default=DEFAULT_PRIVATE / "FactorioPad.ipa")
    parser.add_argument("--dmg", type=Path, default=ROOT / "factorio_mac_2.1.24.dmg")
    parser.add_argument("--sdk", type=Path, default=SDK)
    parser.add_argument("--llvm-bin", type=Path, default=LLVM)
    parser.add_argument("--seven-zip", type=Path, default=SEVENZIP)
    parser.add_argument("--report", type=Path, default=DEFAULT_PRIVATE / "audit" / "original-provider-classification.json")
    args = parser.parse_args()
    try:
        classify(args.ipa, args.dmg, args.sdk, args.llvm_bin, args.seven_zip, args.report)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, struct.error) as error:
        print(f"CLASSIFICATION ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
