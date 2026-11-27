#!/usr/bin/env python3
"""Audit private FactorioGuest Mach-O bindings without extracting FactorioData.

Run on Windows from any working directory:
    python F:/FactoriOS/Tools/audit_macho_imports.py

The script reads only two framework binaries from the existing private IPA.
Full tool output is saved under reports/macho-import-audit; the console is concise.
"""
from __future__ import annotations

import argparse
import json
import struct
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_IPA = ROOT / "dist" / "private-duo-test-2.1.24" / "FactorioPad.ipa"
DEFAULT_LLVM = pathlib.Path(r"C:\Program Files\LLVM\bin")
DEFAULT_SDK = pathlib.Path(r"F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk")
SDK_VERSION = "27.2"
MIN_IOS = "17.0"
FRAMEWORK_BINARY = {
    "guest": "Frameworks/FactorioGuest.framework/FactorioGuest",
    "compat": "Frameworks/FactorioCompat.framework/FactorioCompat",
}


def run_tool(llvm_bin: pathlib.Path, executable: str, *args: str) -> str:
    binary = llvm_bin / (executable + (".exe" if sys.platform == "win32" else ""))
    if not binary.is_file():
        raise RuntimeError(f"LLVM tool not found: {binary}")
    command = [str(binary), *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if result.returncode:
        details = (result.stderr + "\n" + result.stdout).strip()
        raise RuntimeError(f"{executable} returned {result.returncode} for {args!r}: {details[:1600]}")
    return result.stdout


def symbols_defined(nm_output: str) -> set[str]:
    result: set[str] = set()
    for line in nm_output.splitlines():
        fields = line.split()
        if fields and fields[-1].startswith("_"):
            result.add(fields[-1])
    return result


def bindings_for_compat(objdump_output: str) -> set[str]:
    """Parse Mach-O dyld bind-table lines whose dylib is FactorioCompat."""
    result: set[str] = set()
    for line in objdump_output.splitlines():
        if "FactorioCompat" not in line:
            continue
        fields = line.strip().split()
        if fields and re.match(r"^_[A-Za-z?$][\w.$?+-]*$", fields[-1]):
            result.add(fields[-1])
    return result



def macho_reexport_paths(binary: pathlib.Path) -> list[str]:
    """Inspect actual LC_REEXPORT_DYLIB commands; ordinary loads do not qualify."""
    raw = binary.read_bytes()
    if len(raw) < 32 or struct.unpack_from("<I", raw)[0] != 0xFEEDFACF:
        raise ValueError("FactorioCompat is not a thin 64-bit little-endian Mach-O")
    ncmds, sizeofcmds = struct.unpack_from("<II", raw, 16)
    pos, end = 32, 32 + sizeofcmds
    if end > len(raw):
        raise ValueError("Malformed Mach-O load-command range")
    results = []
    for _ in range(ncmds):
        if pos + 8 > end:
            raise ValueError("Truncated Mach-O load command")
        cmd, size = struct.unpack_from("<II", raw, pos)
        if size < 8 or pos + size > end:
            raise ValueError("Invalid Mach-O load-command length")
        if cmd == 0x8000001F:  # LC_REEXPORT_DYLIB, not LC_LOAD_DYLIB
            if size < 24:
                raise ValueError("Truncated reexport load command")
            off = struct.unpack_from("<I", raw, pos + 8)[0]
            if not 24 <= off < size:
                raise ValueError("Invalid reexport install-name offset")
            results.append(raw[pos+off:pos+size].split(b"\0", 1)[0].decode("utf-8", "replace"))
        pos += size
    if pos != end:
        raise ValueError("Malformed Mach-O load-command end")
    return results


def is_iokit_reexport(path: str) -> bool:
    return bool(re.search(r"/IOKit\.framework/(?:Versions/[^/]+/)?IOKit$", path))


def try_sdk_link(symbols: list[str], sdk: pathlib.Path,
                 llvm: pathlib.Path, target_dir: pathlib.Path,
                 label: str) -> tuple[bool, dict[str, str], str]:
    """Prove IOKit imports using a targeted iOS link and provider verification.

    Unlike the previous implementation, this uses -no_fixup_chains so the
    classic dyld bind table is inspectable. If a single-symbol probe links
    but no IOKit bind is printed, an exact-symbol negative-control link
    without IOKit can distinguish the framework requirement.
    """
    source = target_dir / (label + ".c")
    obj = target_dir / (label + ".o")
    dylib = target_dir / (label + ".dylib")
    if not all(re.fullmatch(r"_[A-Za-z0-9_.$?+\-]+", symbol) for symbol in symbols):
        raise ValueError("Unexpected symbol syntax in SDK probe")
    references = [f"extern char factorio_probe_{n} __asm__({json.dumps(symbol)});"
                  for n, symbol in enumerate(symbols)]
    pointers = ", ".join(f"&factorio_probe_{n}" for n in range(len(symbols)))
    source.write_text("\n".join(references) +
                      "\n__attribute__((used)) void * const factorio_probe_refs[] = { " +
                      pointers + " };\n", encoding="utf-8")
    clang = llvm / "clang.exe"
    ld = llvm / "ld64.lld.exe"
    cc = subprocess.run([str(clang), "-target", f"arm64-apple-ios{MIN_IOS}",
                         "-isysroot", str(sdk), "-x", "c", "-c",
                         str(source), "-o", str(obj)],
                        capture_output=True, text=True, errors="replace")
    if cc.returncode:
        raise RuntimeError(f"iOS SDK probe compilation failed: {cc.stderr[-2500:]}")

    # Guard against a wrong asm-label spelling or an optimizer removing the
    # undefined reference. Without this check a linker success proves nothing.
    obj_undefined = run_tool(llvm, "llvm-nm", "--undefined-only", str(obj))
    undefined = symbols_defined(obj_undefined)
    absent = sorted(set(symbols) - undefined)
    if absent:
        raise RuntimeError(
            f"SDK probe object does not reference the EXACT required symbols: {absent}. "
            f"Object imports: {obj_undefined[-1800:]}")

    base = [str(ld), "-dylib", "-arch", "arm64", "-platform_version",
            "ios", MIN_IOS, SDK_VERSION, "-syslibroot", str(sdk),
            "-undefined", "error", "-no_fixup_chains", "-lSystem"]
    with_iokit = subprocess.run(base + ["-framework", "IOKit", "-o", str(dylib), str(obj)],
                                capture_output=True, text=True, errors="replace")
    if with_iokit.returncode:
        return False, {}, (
            "iOS-arm64 linker could not resolve requested symbols with IOKit: " +
            (with_iokit.stderr + "\n" + with_iokit.stdout)[-2000:])

    expected = set(symbols)
    found: dict[str, str] = {}
    bind_diagnostics: list[str] = []
    for flag in ("--bind", "--lazy-bind"):
        output = run_tool(llvm, "llvm-objdump", "--macho", flag, str(dylib))
        bind_diagnostics.append(flag + ": " + output[-1800:])
        for line in output.splitlines():
            cols = line.strip().split()
            if len(cols) < 2 or cols[-1] not in expected:
                continue
            if "IOKit" in cols[-2]:
                found[cols[-1]] = "direct Mach-O bind: " + line.strip()

    if len(symbols) == 1 and symbols[0] not in found:
        # A positive link is not enough: compare the SAME object with IOKit
        # omitted. If this fails but the positive link succeeds, the exact
        # unresolved input requires IOKit (including its SDK reexports).
        no_iokit = target_dir / (label + "-no-iokit.dylib")
        negative = subprocess.run(base + ["-o", str(no_iokit), str(obj)],
                                  capture_output=True, text=True, errors="replace")
        if negative.returncode:
            found[symbols[0]] = (
                "positive iOS-arm64 link with IOKit, negative control WITHOUT "
                "IOKit failed for same exact-symbol object; linker contrast")
        else:
            return True, found, (
                "LINK SUCCEEDED EVEN WITHOUT IOKit; cannot credit its reexport. " +
                "Dyld binding excerpt:\n" + "\n".join(bind_diagnostics)[-2600:])

    return True, found, (
        "SDK linker accepted symbols, but not all provider bindings were "
        "confirmed. Inspect classic dyld binding excerpts:\n" +
        "\n".join(bind_diagnostics)[-2600:]) if len(found) != len(symbols) else ""


def probe_iokit_symbols(symbols: list[str], sdk: pathlib.Path,
                        llvm: pathlib.Path, tempdir: pathlib.Path,
                        report_dir: pathlib.Path
                        ) -> tuple[dict[str, str], dict[str, str]]:
    """Resolve SDK candidates with group probes and exact negative controls.

    A successful group link is efficient; ambiguous symbols are bisected
    until each has independent evidence. No unresolved symbol is silently
    marked as satisfied merely because its spelling appears in an SDK stub.
    """
    if not sdk.is_dir():
        raise FileNotFoundError(f"Cannot verify iOS-arm64 IOKit exports without SDK: {sdk}")
    for name in ("clang.exe", "ld64.lld.exe", "llvm-nm.exe", "llvm-objdump.exe"):
        if not (llvm / name).is_file():
            raise FileNotFoundError(f"SDK-link probe tool missing: {llvm / name}")
    verified: dict[str, str] = {}
    unverified: dict[str, str] = {}
    attempts: list[dict[str, object]] = []
    attempt = 0

    def check(group: list[str]) -> None:
        nonlocal attempt
        if not group:
            return
        attempt += 1
        ok, bound, detail = try_sdk_link(group, sdk, llvm, tempdir, f"probe_{attempt}")
        attempts.append({"symbols": group, "linked_with_iokit": ok,
                         "verified_symbols": list(bound), "diagnostic": detail})
        verified.update(bound)
        remaining = [x for x in group if x not in bound]
        if not remaining:
            return
        if len(remaining) == 1:
            symbol = remaining[0]
            # If this came from a multi-symbol link, isolate it to get its
            # own positive/negative controls before recording a conclusion.
            if len(group) != 1:
                check([symbol])
            else:
                unverified[symbol] = detail or "SDK provider not demonstrated"
            return
        if not ok or len(remaining) > 1:
            mid = len(remaining) // 2
            check(remaining[:mid])
            check(remaining[mid:])

    check(symbols)
    (report_dir / "link-probe-attempts.json").write_text(
        json.dumps(attempts, indent=2), encoding="utf-8")
    return verified, unverified



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=pathlib.Path, default=DEFAULT_IPA)
    parser.add_argument("--llvm-bin", type=pathlib.Path, default=DEFAULT_LLVM)
    parser.add_argument("--sdk", type=pathlib.Path, default=DEFAULT_SDK,
                        help="Extracted genuine iPhoneOS 27.2 SDK for arm64 linker validation")
    parser.add_argument("--report-dir", type=pathlib.Path, default=ROOT / "reports" / "macho-import-audit")
    args = parser.parse_args()

    if not args.ipa.is_file():
        raise FileNotFoundError(f"Private IPA not found: {args.ipa}")
    args.report_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="factorios-audit-") as temp:
        tempdir = pathlib.Path(temp)
        extracted: dict[str, pathlib.Path] = {}
        with zipfile.ZipFile(args.ipa) as ipa:
            if ipa.testzip() is not None:
                raise ValueError("Private IPA failed ZIP integrity check")
            for role, suffix in FRAMEWORK_BINARY.items():
                candidates = [n for n in ipa.namelist()
                              if n.startswith("Payload/") and n.endswith("/" + suffix)]
                if len(candidates) != 1:
                    raise ValueError(f"Expected one {role} framework binary in IPA; found {len(candidates)}")
                target = tempdir / role
                with ipa.open(candidates[0]) as source, target.open("wb") as dest:
                    shutil.copyfileobj(source, dest)
                extracted[role] = target

        # Save the complete reports; do not print thousands of bindings over SSH.
        export_text = run_tool(args.llvm_bin, "llvm-nm", "--extern-only",
                               "--defined-only", str(extracted["compat"]))
        (args.report_dir / "compat-exports.txt").write_text(export_text, encoding="utf-8")
        exports = symbols_defined(export_text)

        used_text = run_tool(args.llvm_bin, "llvm-objdump", "--macho",
                             "--dylibs-used", str(extracted["guest"]))
        (args.report_dir / "guest-dylibs.txt").write_text(used_text, encoding="utf-8")

        collected: dict[str, set[str]] = {}
        for name, flag in (("strong", "--bind"), ("lazy", "--lazy-bind"),
                           ("weak", "--weak-bind")):
            output = run_tool(args.llvm_bin, "llvm-objdump", "--macho",
                              flag, str(extracted["guest"]))
            (args.report_dir / f"guest-{name}-binds.txt").write_text(output, encoding="utf-8")
            collected[name] = bindings_for_compat(output)

        required = collected["strong"] | collected["lazy"]
        optional = collected["weak"]
        missing_direct = sorted(required - exports)
        # Keep this historical direct-export file for the source classifier.
        (args.report_dir / "missing-strong-compat-exports.txt").write_text(
            "\n".join(missing_direct) + ("\n" if missing_direct else ""),
            encoding="utf-8")
        (args.report_dir / "missing-direct-compat-exports.txt").write_text(
            "\n".join(missing_direct) + ("\n" if missing_direct else ""),
            encoding="utf-8")

        reexports = macho_reexport_paths(extracted["compat"])
        (args.report_dir / "compat-reexport-loads.txt").write_text(
            "\n".join(reexports) + ("\n" if reexports else ""),
            encoding="utf-8")
        verified_iokit: dict[str, str] = {}
        unverified_reexport: dict[str, str] = {}
        if missing_direct and any(is_iokit_reexport(path) for path in reexports):
            verified_iokit, unverified_reexport = probe_iokit_symbols(
                missing_direct, args.sdk, args.llvm_bin, tempdir, args.report_dir)
        genuine_remaining = sorted(set(missing_direct) - set(verified_iokit))
        (args.report_dir / "verified-iokit-reexports.txt").write_text(
            "\n".join(sorted(verified_iokit)) + ("\n" if verified_iokit else ""),
            encoding="utf-8")
        (args.report_dir / "unresolved-strong-compat-exports.txt").write_text(
            "\n".join(genuine_remaining) + ("\n" if genuine_remaining else ""),
            encoding="utf-8")
        evidence = {
            "scope": "FactorioGuest imports bound to FactorioCompat only",
            "compat_defined_exports": len(exports),
            "strong_and_lazy_compat_bindings": len(required),
            "weak_compat_bindings": len(optional),
            "missing_direct_exports": len(missing_direct),
            "reexport_load_commands": reexports,
            "verified_iokit_reexports": verified_iokit,
            "sdk_probe_unverified_reasons": {
                key: unverified_reexport.get(key, "No matching verified IOKit reexport; investigate original provider and ABI")
                for key in genuine_remaining
            },
            "remaining_unverified_strong": genuine_remaining,
            "platform": f"arm64-apple-ios{MIN_IOS}",
            "sdk": str(args.sdk),
            "warning": "This check does not prove runtime iOS symbol availability or audit guest bindings assigned directly to other system frameworks.",
        }
        (args.report_dir / "reexport-resolution.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8")

        print(f"Private IPA: {args.ipa}")
        print(f"FactorioCompat directly defined exports: {len(exports)}")
        print(f"FactorioCompat strong/lazy guest bindings: {len(required)}")
        print(f"FactorioCompat weak guest bindings: {len(optional)}")
        print(f"Missing strong/lazy DIRECT exports: {len(missing_direct)}")
        print(f"Verified via native IOKit LC_REEXPORT_DYLIB and iOS-arm64 SDK link: {len(verified_iokit)}")
        print(f"REMAINING UNVERIFIED strong/lazy FactorioCompat bindings: {len(genuine_remaining)}")
        for symbol in genuine_remaining[:60]:
            print(f"  UNRESOLVED {symbol}")
        if not required:
            print("WARNING: no FactorioCompat bindings were recognized; inspect the saved bind tables.")
            print(f"Reports: {args.report_dir}")
            return 2
        print("NOTE: Other system-framework bindings and actual device runtime remain outside this audit's scope.")
        print(f"Reports: {args.report_dir}")
        return 1 if genuine_remaining else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"AUDIT ERROR: {error}", file=sys.stderr)
        sys.exit(3)
