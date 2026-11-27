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
from patch_factorio import SHIM_FRAMEWORKS

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


PROVIDER_LINK_FLAGS = {
    "IOKit": ["-framework", "IOKit"],
    "MobileCoreServices": ["-framework", "MobileCoreServices"],
    "CoreServices": ["-framework", "CoreServices"],
    "libSystem": ["-lSystem"],
    # These are direct FactorioGuest native iOS imports, not libraries
    # whose macOS dependency was rewritten to FactorioCompat. Keep them
    # direct and validate their symbols against the genuine iPhoneOS SDK.
    "AVFoundation": ["-framework", "AVFoundation"],
    "CoreMedia": ["-framework", "CoreMedia"],
    "UniformTypeIdentifiers": ["-framework", "UniformTypeIdentifiers"],
    "libresolv": ["-lresolv"],
    # Frameworks that FactorioGuest binds directly to. Their original
    # macOS exports are not guaranteed to exist in the iPhoneOS SDK.
    "Foundation": ["-framework", "Foundation"],
    "CoreFoundation": ["-framework", "CoreFoundation"],
    "CoreGraphics": ["-framework", "CoreGraphics"],
    "CoreVideo": ["-framework", "CoreVideo"],
    "CoreAudio": ["-framework", "CoreAudio"],
    "AudioToolbox": ["-framework", "AudioToolbox"],
    "Metal": ["-framework", "Metal"],
    "Security": ["-framework", "Security"],
    "UIKit": ["-framework", "UIKit"],
    "QuartzCore": ["-framework", "QuartzCore"],
    "AVFAudio": ["-framework", "AVFAudio"],
    "GameController": ["-framework", "GameController"],
    "libobjc": ["-lobjc"],
    "libc++": ["-lc++"],
    "libz": ["-lz"],
    "libsqlite3": ["-lsqlite3"],
    "libcompression": ["-lcompression"],
    "libiconv": ["-liconv"],
    "libxml2": ["-lxml2"],
    "libdispatch": ["-ldispatch"],
    "libc++abi": ["-lc++abi"],
}


def native_provider_from_line(line: str) -> tuple[str | None, str | None]:
    """Return (normalized SDK provider, symbol) for a native guest import."""
    cols = line.strip().split()
    if len(cols) < 3 or not re.fullmatch(r"_[A-Za-z0-9_.$?+-]+", cols[-1]):
        return None, None
    raw_provider = cols[-2]
    if "FactorioCompat" in raw_provider:
        return None, None
    # Match complete provider basenames; CoreFoundation must not be mistaken
    # for Foundation. llvm-objdump may show names or full install paths.
    name = raw_provider.split("/")[-1]
    if name.endswith(".dylib"):
        name = re.sub(r"(?:\.[A-Za-z0-9]+)?\.dylib$", "", name)
    if name in PROVIDER_LINK_FLAGS:
        return name, cols[-1]
    # Known framework install-name aliases (including macOS versioned paths).
    frame = re.search(r"/([^/]+)\.framework/(?:Versions/[^/]+/)?[^/]+$", raw_provider)
    if frame and frame.group(1) in PROVIDER_LINK_FLAGS:
        return frame.group(1), cols[-1]
    return raw_provider, cols[-1]


def provider_matches_binding(provider: str, raw_line: str) -> bool:
    """Confirm the actual library written into a successful probe's dyld bind."""
    fields = raw_line.split()
    if len(fields) < 2:
        return False
    dyld_provider = fields[-2]
    if provider == "libSystem":
        # libSystem's umbrella reexports can bind to libSystem.B.dylib
        # or /usr/lib/system/ libraries depending on SDK/linker versions.
        return ("libSystem" in dyld_provider or
                re.search(r"/usr/lib/system/lib[^/]+\.dylib$", dyld_provider) is not None)
    # Exact normalized provider identity, not a substring: Foundation and
    # CoreFoundation must never be conflated in the guest validation.
    resolved, _symbol = native_provider_from_line(raw_line)
    return resolved == provider


def try_provider_link(symbols: list[str], provider: str, sdk: pathlib.Path,
                      llvm: pathlib.Path, target_dir: pathlib.Path,
                      label: str, provider_flags: list[str] | None = None,
                      permitted_providers: set[str] | None = None
                      ) -> tuple[bool, dict[str, str], str]:
    """Compile exact symbols, link against one candidate provider, and validate binds.

    Positive and negative controls use the SAME object. A text match in a
    .tbd file cannot pass this probe. Failed links produce raw diagnostics.
    """
    source = target_dir / (label + ".c")
    obj = target_dir / (label + ".o")
    dylib = target_dir / (label + ".dylib")
    if not all(re.fullmatch(r"_[A-Za-z0-9_.$?+\-]+", symbol) for symbol in symbols):
        raise ValueError(f"Unexpected guest symbol syntax in {provider} probe")
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

    obj_undefined = run_tool(llvm, "llvm-nm", "--undefined-only", str(obj))
    undefined = symbols_defined(obj_undefined)
    absent = sorted(set(symbols) - undefined)
    if absent:
        raise RuntimeError(
            f"SDK probe object does not reference exact guest symbols: {absent}. "
            f"Object imports: {obj_undefined[-1800:]}")

    base = [str(ld), "-dylib", "-arch", "arm64", "-platform_version",
            "ios", MIN_IOS, SDK_VERSION, "-syslibroot", str(sdk),
            "-undefined", "error", "-no_fixup_chains"]
    # For individual framework probes keep libSystem in both controls.
    # For the combined reexport probe, include libSystem only in the positive
    # set so its symbols also receive a meaningful negative control.
    if provider not in ("libSystem", "__all_reexports__"):
        base += ["-lSystem"]
    positive_flags = (
        PROVIDER_LINK_FLAGS[provider] if provider_flags is None else provider_flags
    )
    with_provider = subprocess.run(
        base + positive_flags + ["-o", str(dylib), str(obj)],
        capture_output=True, text=True, errors="replace")
    if with_provider.returncode:
        return False, {}, (
            f"iOS-arm64 linker could not resolve requested symbols WITH {provider}: " +
            (with_provider.stderr + "\n" + with_provider.stdout)[-2400:])

    expected = set(symbols)
    found: dict[str, str] = {}
    details: list[str] = []
    for flag in ("--bind", "--lazy-bind"):
        output = run_tool(llvm, "llvm-objdump", "--macho", flag, str(dylib))
        details.append(flag + ": " + output[-1300:])
        for line in output.splitlines():
            fields = line.strip().split()
            if len(fields) < 2 or fields[-1] not in expected:
                continue
            if provider == "__all_reexports__":
                valid_bind = any(
                    provider_matches_binding(item, line)
                    for item in (permitted_providers or set())
                )
            else:
                valid_bind = provider_matches_binding(provider, line)
            if valid_bind:
                found[fields[-1]] = "native Mach-O bind: " + line.strip()

    if len(symbols) == 1 and symbols[0] not in found:
        without_provider = target_dir / (label + "-negative.dylib")
        negative = subprocess.run(
            base + ["-o", str(without_provider), str(obj)],
            capture_output=True, text=True, errors="replace")
        if negative.returncode:
            found[symbols[0]] = (
                f"positive iOS-arm64 SDK link WITH {provider}; exact-symbol "
                f"negative link WITHOUT {provider} failed")
        else:
            return True, found, (
                f"LINK ALSO SUCCEEDED WITHOUT {provider}; cannot attribute it. "
                + "\n".join(details)[-2200:])

    return True, found, (
        f"SDK link with {provider} passed, but provider not established for "
        f"{sorted(set(symbols)-set(found))}. Dyld evidence:\n" +
        "\n".join(details)[-2400:]) if len(found) != len(symbols) else ""


def probe_provider_symbols(symbols: list[str], provider: str,
                           sdk: pathlib.Path, llvm: pathlib.Path,
                           tempdir: pathlib.Path, report_dir: pathlib.Path,
                           provider_flags: list[str] | None = None,
                           permitted_providers: set[str] | None = None
                           ) -> tuple[dict[str, str], dict[str, str]]:
    """Bisect ambiguous imports until each has direct or linker-control evidence."""
    if not sdk.is_dir():
        raise FileNotFoundError(f"Cannot verify iOS-arm64 exports without SDK: {sdk}")
    for name in ("clang.exe", "ld64.lld.exe", "llvm-nm.exe", "llvm-objdump.exe"):
        if not (llvm / name).is_file():
            raise FileNotFoundError(f"SDK-link probe tool missing: {llvm / name}")
    verified: dict[str, str] = {}
    unverified: dict[str, str] = {}
    attempts: list[dict[str, object]] = []
    count = 0

    def check(group: list[str]) -> None:
        nonlocal count
        if not group:
            return
        count += 1
        ok, bound, diagnostic = try_provider_link(
            group, provider, sdk, llvm, tempdir, f"{provider}_{count}",
            provider_flags=provider_flags,
            permitted_providers=permitted_providers)
        attempts.append({"symbols": group, "linked_with_provider": ok,
                         "verified_symbols": list(bound), "diagnostic": diagnostic})
        verified.update(bound)
        remaining = [name for name in group if name not in bound]
        if not remaining:
            return
        if len(remaining) == 1:
            if len(group) != 1:
                check([remaining[0]])
            else:
                unverified[remaining[0]] = diagnostic or "Provider not demonstrated"
            return
        mid = len(remaining) // 2
        check(remaining[:mid])
        check(remaining[mid:])

    check(symbols)
    (report_dir / f"link-probe-attempts-{provider}.json").write_text(
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
        bind_outputs: dict[str, str] = {}
        for name, flag in (("strong", "--bind"), ("lazy", "--lazy-bind"),
                           ("weak", "--weak-bind")):
            output = run_tool(args.llvm_bin, "llvm-objdump", "--macho",
                              flag, str(extracted["guest"]))
            bind_outputs[name] = output
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
        # Every native SDK framework that the original upstream guest
        # patcher redirects to FactorioCompat must be checked as a real
        # reexport. The former audit checked just IOKit/MobileCoreServices/
        # libSystem, silently ignoring Foundation and CoreGraphics.
        expected_frameworks = sorted(
            SHIM_FRAMEWORKS.intersection(PROVIDER_LINK_FLAGS)
            | {"MobileCoreServices"}
        )
        def framework_reexport_paths(provider: str) -> list[str]:
            regex = re.compile(
                r"/" + re.escape(provider)
                + r"\.framework/(?:Versions/[^/]+/)?"
                + re.escape(provider) + r"$")
            return [path for path in reexports if regex.search(path)]

        provider_reexport_paths = {
            name: framework_reexport_paths(name) for name in expected_frameworks
        }
        provider_reexport_paths["libSystem"] = [
            name for name in reexports
            if re.search(r"/libSystem(?:\.B)?\.dylib$", name)
        ]
        # The extracted SDK may not include CoreServices.framework;
        # MobileCoreServices supplies iOS legacy UTType exports instead.
        if not provider_reexport_paths.get("CoreServices"):
            provider_reexport_paths.pop("CoreServices", None)
        verified_by_provider: dict[str, dict[str, str]] = {}
        unverified_by_provider: dict[str, dict[str, str]] = {}
        outstanding = list(missing_direct)
        # One combined SDK linker probe matches how FactorioCompat itself
        # reexports all native providers. The previous algorithm ran a
        # recursive per-symbol linker search against EVERY framework: with
        # hundreds of upstream-routed imports this became extremely costly
        # even though most were legitimate iOS symbols from other providers.
        active_providers = [
            name for name in provider_reexport_paths
            if provider_reexport_paths[name]
        ]
        combined_flags: list[str] = []
        for provider in active_providers:
            combined_flags.extend(PROVIDER_LINK_FLAGS[provider])
        if outstanding and combined_flags:
            verified, rejected = probe_provider_symbols(
                outstanding, "__all_reexports__", args.sdk, args.llvm_bin,
                tempdir, args.report_dir, provider_flags=combined_flags,
                permitted_providers=set(active_providers))
            verified_by_provider["combined_reexports"] = verified
            unverified_by_provider["combined_reexports"] = rejected
            outstanding = sorted(set(outstanding) - set(verified))
        genuine_remaining = outstanding
        verified_iokit = {
            symbol: evidence
            for symbol, evidence in verified_by_provider.get("combined_reexports", {}).items()
            if "IOKit" in evidence
        }
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
            "provider_reexport_paths": provider_reexport_paths,
            "verified_iokit_reexports": verified_iokit,
            "verified_by_provider": verified_by_provider,
            "probe_failures_by_provider": unverified_by_provider,
            "remaining_unverified_strong": genuine_remaining,
            "platform": f"arm64-apple-ios{MIN_IOS}",
            "sdk": str(args.sdk),
            "warning": "SDK link probes verify arm64/iOS export availability but cannot prove actual device runtime or image loading.",
        }
        (args.report_dir / "reexport-resolution.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8")

        # The original scoped audit missed imports that still targeted iOS
        # Foundation/CoreGraphics despite already having compatible shims.
        # These device-proven blockers must have explicit FactorioCompat binds
        # and exports in the actual packaged binaries.
        known_compat_imports = {
            "_OBJC_CLASS_$_NSAppleEventManager": "Foundation",
            "_kCGDisplayShowDuplicateLowResolutionModes": "CoreGraphics",
        }
        known_routings: dict[str, list[str]] = {}
        invalid_known: dict[str, str] = {}
        for known_symbol, native_framework in known_compat_imports.items():
            rows = [
                line.strip()
                for name in ("strong", "lazy")
                for line in bind_outputs[name].splitlines()
                if line.strip().split()[-1:] == [known_symbol]
            ]
            known_routings[known_symbol] = rows
            if not rows or any("FactorioCompat" not in row for row in rows):
                invalid_known[known_symbol] = (
                    f"Still bound to native {native_framework}, or no strong/lazy "
                    f"binding found: {rows}")
            elif known_symbol not in exports:
                invalid_known[known_symbol] = (
                    "Rebound correctly but missing export in packaged FactorioCompat")
        if invalid_known:
            for symbol, reason in invalid_known.items():
                print(f"ERROR: {symbol}: {reason}")

        # Audit all other strong/lazy bindings against their native providers,
        # not just the imports routed through FactorioCompat.
        native_groups: dict[str, set[str]] = {}
        native_binding_rows: dict[str, list[str]] = {}
        for name in ("strong", "lazy"):
            for line in bind_outputs[name].splitlines():
                provider, symbol = native_provider_from_line(line)
                if provider is None or symbol is None:
                    continue
                native_groups.setdefault(provider, set()).add(symbol)
                native_binding_rows.setdefault(provider, []).append(line.strip())
        native_verified: dict[str, dict[str, str]] = {}
        native_unverified: dict[str, dict[str, str]] = {}
        for provider, symbols in sorted(native_groups.items()):
            if provider not in PROVIDER_LINK_FLAGS:
                native_unverified[provider] = {
                    symbol: "Unknown SDK native binding provider. "
                            "Inspect original Mach-O library ordinal."
                    for symbol in sorted(symbols)}
                continue
            success, rejected = probe_provider_symbols(
                sorted(symbols), provider, args.sdk, args.llvm_bin,
                tempdir, args.report_dir)
            native_verified[provider] = success
            native_unverified[provider] = rejected
        (args.report_dir / "native-provider-resolution.json").write_text(
            json.dumps({
                "guest_native_imports_by_provider": {
                    k: sorted(v) for k, v in native_groups.items()},
                "native_sdk_verified": native_verified,
                "unverified_native_imports": native_unverified,
                "native_binding_rows": native_binding_rows,
                "known_compat_symbol_routings": known_routings,
                "invalid_known_compat_routings": invalid_known,
                "note": "Positive SDK link probes do not prove on-device dyld behavior.",
            }, indent=2), encoding="utf-8")
        total_native_missing = sum(len(v) for v in native_unverified.values())

        print(f"Private IPA: {args.ipa}")
        print(f"FactorioCompat directly defined exports: {len(exports)}")
        print(f"FactorioCompat strong/lazy guest bindings: {len(required)}")
        print(f"FactorioCompat weak guest bindings: {len(optional)}")
        print(f"Missing strong/lazy DIRECT exports: {len(missing_direct)}")
        for provider, verified in verified_by_provider.items():
            print(f"Verified via {provider} iOS-arm64 SDK linker probe: {len(verified)}")
        print(f"REMAINING UNVERIFIED strong/lazy FactorioCompat bindings: {len(genuine_remaining)}")
        print(f"Native strong/lazy bindings tested: {sum(map(len, native_groups.values()))}")
        print(f"Native strong/lazy provider imports unverified: {total_native_missing}")
        for symbol in genuine_remaining[:60]:
            print(f"  UNRESOLVED {symbol}")
        if not required:
            print("WARNING: no FactorioCompat bindings were recognized; inspect the saved bind tables.")
            print(f"Reports: {args.report_dir}")
            return 2
        print("NOTE: SDK export verification is host-side only; device dyld, initialization and gameplay remain untested.")
        print(f"Reports: {args.report_dir}")
        if invalid_known:
            print("Known macOS-only Foundation/CoreGraphics device failures remain in packaged guest.")
        for provider, symbols in sorted(native_unverified.items()):
            if symbols:
                print(f"  NATIVE UNVERIFIED {provider}: {len(symbols)} symbols")
                for symbol in list(symbols)[:12]:
                    print(f"    {symbol}")
        return 1 if genuine_remaining or total_native_missing or invalid_known else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"AUDIT ERROR: {error}", file=sys.stderr)
        sys.exit(3)
