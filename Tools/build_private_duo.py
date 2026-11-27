#!/usr/bin/env python3
"""Rebuild native iOS 27.2 FactoriOS and privately package Factorio 2.1.24.

Run on the Windows build host, with no nested PowerShell commands:
    python F:/FactoriOS/Tools/build_private_duo.py --inventory
    python F:/FactoriOS/Tools/build_private_duo.py

If the DMG is outside the listed folders, specify --dmg PATH when invoking
Python on Windows. The separate FactorioData folder is never read or modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
SEVEN_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")
LLVM = Path(os.environ.get("LLVM_BIN", r"C:\Program Files\LLVM\bin"))
SKIP_FOLDERS = {"FactorioData", ".git", "node_modules", "Builds", "Objects", "ModuleCache"}
STATUS_FILE = DIST / "build_private_duo_status.json"


def show_status() -> int:
    if not STATUS_FILE.is_file():
        print(f"No recorded build status yet: {STATUS_FILE}", flush=True)
        return 1
    status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    print(json.dumps(status, indent=2), flush=True)
    log = Path(status.get("log", ""))
    if log.is_file():
        with log.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 8000))
            excerpt = stream.read().decode("utf-8", errors="replace")
        print("---- Latest build log ----", flush=True)
        print(excerpt, flush=True)
    # The private IPA and its audit may exist even if the final stage failed.
    # Surface both without rebuilding, uploading game content, or shell parsing.
    ipa_value = status.get("ipa")
    if ipa_value:
        ipa = Path(ipa_value)
        if ipa.is_file():
            print(f"---- Existing private IPA ----\n{ipa}", flush=True)
            print(f"IPA SHA-256: {sha256_file(ipa)}", flush=True)
            try:
                with zipfile.ZipFile(ipa) as archive:
                    for suffix in (
                        "/Frameworks/FactorioGuest.framework/FactorioGuest",
                        "/Frameworks/FactorioCompat.framework/FactorioCompat",
                    ):
                        matches = [n for n in archive.namelist()
                                   if n.startswith("Payload/") and n.endswith(suffix)]
                        if len(matches) == 1:
                            print(f"{Path(suffix).name} SHA-256: "
                                  f"{sha256_zip_member(archive, matches[0])}", flush=True)
                        else:
                            print(f"Cannot uniquely locate embedded {suffix} (found {len(matches)})", flush=True)
            except (OSError, zipfile.BadZipFile, RuntimeError) as error:
                print(f"IPA inspection error: {error}", flush=True)
            audit_output = ipa.parent / "audit-output.txt"
            if audit_output.is_file():
                print(f"---- Full saved audit summary: {audit_output} ----", flush=True)
                print(audit_output.read_text(encoding="utf-8", errors="replace")[-16000:], flush=True)
            missing = ipa.parent / "audit" / "missing-strong-compat-exports.txt"
            if missing.is_file():
                names = [line.strip() for line in missing.read_text(
                    encoding="utf-8", errors="replace").splitlines() if line.strip()]
                print(f"---- Missing direct FactorioCompat exports: {len(names)} ----", flush=True)
                print("\n".join(names[:200]), flush=True)
        else:
            print(f"Status references missing IPA: {ipa}", flush=True)
    return 0


def report_status(stage: str, state: str, tag: str, logfile: Path, **extra: object) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    previous = {}
    if STATUS_FILE.is_file():
        try:
            previous = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
    if previous.get("tag") != tag:
        previous = {}
    # Stage transitions must not inherit terminal failure codes from an
    # earlier attempt with the same tag. An audit-only rerun can pass while
    # the old status otherwise continues displaying audit_exit_code=1.
    for stale_failure_key in ("exit_code", "audit_exit_code", "error"):
        previous.pop(stale_failure_key, None)
    payload = {
        **previous,
        "tag": tag,
        "pid": os.getpid(),
        "stage": stage,
        "state": state,
        "log": str(logfile),
        "updated": datetime.now().isoformat(timespec="seconds"),
        **extra,
    }
    temp = STATUS_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temp, STATUS_FILE)
    print(f"[{state.upper()}] {stage}; status={STATUS_FILE}; log={logfile}", flush=True)


def run_logged(args: list[str], stage: str, tag: str, logfile: Path) -> None:
    report_status(stage, "running", tag, logfile)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    command = list(args)
    if command[0] == sys.executable and len(command) > 1 and command[1] != "-u":
        command.insert(1, "-u")  # flush subprocess progress while its stage is running
    with logfile.open("a", encoding="utf-8") as output:
        output.write(f"\n==== {datetime.now().isoformat()} {stage} ====\n")
        output.flush()
        completed = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT,
                                   text=True, errors="replace")
    if completed.returncode:
        report_status(stage, "failed", tag, logfile, exit_code=completed.returncode)
        raise RuntimeError(f"{stage} failed (exit {completed.returncode}); see {logfile}")
    report_status(stage, "completed", tag, logfile)


def run(args: list[str], *, accepted: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, capture_output=True, text=True, errors="replace")
    if completed.stdout:
        print(completed.stdout[-3500:])
    if completed.stderr:
        print(completed.stderr[-1800:], file=sys.stderr)
    if completed.returncode not in accepted:
        raise RuntimeError(f"Command returned {completed.returncode}: {args[0]} {args[1] if len(args)>1 else ''}")
    return completed


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_zip_member(ipa: zipfile.ZipFile, name: str) -> str:
    digest = hashlib.sha256()
    with ipa.open(name) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_dmgs() -> list[Path]:
    """Bounded, nonrecursive candidate search; never descend into FactorioData."""
    bases = [
        ROOT, ROOT / "input", ROOT / "inputs", ROOT / "dist",
        Path("F:/"), Path("F:/Downloads"), Path("F:/Games"),
        Path("F:/NXNative"), Path("F:/FactoriOS"),
    ]
    candidates = set()
    for base in bases:
        if not base.is_dir() or base.name in SKIP_FOLDERS:
            continue
        for pattern in ("*.dmg", "*/*.dmg"):
            try:
                for file in base.glob(pattern):
                    if file.is_file() and "factorio" in file.name.lower():
                        candidates.add(file.resolve())
            except (OSError, PermissionError):
                continue
    return sorted(candidates, key=lambda p: str(p).lower())


def describe_host(dmgs: list[Path]) -> None:
    print(f"Repository: {ROOT}")
    print(f"Python: {sys.executable}")
    print(f"LLVM: {LLVM}")
    print(f"7-Zip: {SEVEN_ZIP} present={SEVEN_ZIP.is_file()}")
    print(f"DMG candidates: {len(dmgs)}")
    for item in dmgs[:15]:
        print(f"  {item}")
    if len(dmgs) > 15:
        print(f"  ... {len(dmgs)-15} more")
    for name in ("build_windows_template.py", "audit_macho_imports.py", "patch_factorio.py"):
        print(f"Tool present {name}: {(ROOT / 'Tools' / name).is_file()}")
    print(f"Companion present: {(ROOT / 'Companion' / 'package_ipa.py').is_file()}")


def verify_output(ipa_path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(ipa_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Private IPA CRC validation failed")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise RuntimeError("Duplicate IPA entries")
        if any("/FactorioData/" in name for name in names):
            raise RuntimeError("New private IPA unexpectedly embeds FactorioData")
        app = "Payload/FactorioPad.app/"
        required = {
            "app": app + "FactorioPad",
            "guest": app + "Frameworks/FactorioGuest.framework/FactorioGuest",
            "compat": app + "Frameworks/FactorioCompat.framework/FactorioCompat",
            "guest_plist": app + "Frameworks/FactorioGuest.framework/Info.plist",
        }
        if any(value not in names for value in required.values()):
            raise RuntimeError("Missing expected guest/compat/app files in IPA")
        info = plistlib.loads(archive.read(required["guest_plist"]))
        if info.get("CFBundleShortVersionString") != "2.1.24":
            raise RuntimeError("Wrong FactorioGuest version (expected 2.1.24)")
        for name in (required["app"], required["guest"], required["compat"]):
            if not ((archive.getinfo(name).external_attr >> 16) & 0o111):
                raise RuntimeError(f"Missing executable permission: {name}")
        guest_sha = sha256_zip_member(archive, required["guest"])
        compat_sha = sha256_zip_member(archive, required["compat"])
        with __import__("tempfile").TemporaryDirectory(prefix="factorios-private-verify-") as tmp:
            guest_bin = Path(tmp) / "FactorioGuest"
            compat_bin = Path(tmp) / "FactorioCompat"
            guest_bin.write_bytes(archive.read(required["guest"]))
            compat_bin.write_bytes(archive.read(required["compat"]))
            objdump = LLVM / "llvm-objdump.exe"
            nm = LLVM / "llvm-nm.exe"
            dependency_report = subprocess.run(
                [str(objdump), "--macho", "--dylibs-used", str(guest_bin)],
                capture_output=True, text=True, errors="replace", check=True).stdout
            # Compare against the *original upstream* Mach-O guest routing:
            # Foundation, CoreGraphics and other macOS framework ordinals are
            # rewritten to FactorioCompat. They must not silently revert to
            # direct native iOS libraries on another Windows build.
            from patch_factorio import SHIM_FRAMEWORKS
            expected_compat = "@rpath/FactorioCompat.framework/FactorioCompat"
            if expected_compat not in dependency_report:
                raise RuntimeError("Guest does not load the upstream FactorioCompat dependency")
            stale_native = [
                framework for framework in sorted(SHIM_FRAMEWORKS)
                if f"/{framework}.framework/{framework}" in dependency_report
                or f"/{framework}.framework/Versions/A/{framework}" in dependency_report
            ]
            if stale_native:
                raise RuntimeError(
                    f"Guest uses native framework paths instead of upstream FactorioCompat: "
                    f"{stale_native}. Restore canonical patch_factorio.py routing.")
            # Device logs show two macOS-only symbols were incorrectly
            # bound to iOS native frameworks even though the compatibility
            # framework already exports both. Check BOTH the dyld provider
            # and the packaged compatibility export before accepting an IPA.
            required_compat_routings = {
                "_OBJC_CLASS_$_NSAppleEventManager": "Foundation",
                "_kCGDisplayShowDuplicateLowResolutionModes": "CoreGraphics",
            }
            dyld_binds: dict[str, list[str]] = {
                symbol: [] for symbol in required_compat_routings
            }
            for bind_flag in ("--bind", "--lazy-bind"):
                binding_report = subprocess.run(
                    [str(objdump), "--macho", bind_flag, str(guest_bin)],
                    capture_output=True, text=True, errors="replace",
                    check=True).stdout
                for line in binding_report.splitlines():
                    cols = line.strip().split()
                    if cols and cols[-1] in dyld_binds:
                        dyld_binds[cols[-1]].append(line.strip())
            for symbol, old_provider in required_compat_routings.items():
                rows = dyld_binds[symbol]
                if not rows or not all("FactorioCompat" in row for row in rows):
                    raise RuntimeError(
                        f"{symbol} is still bound to native {old_provider} "
                        f"rather than FactorioCompat: {rows}")
            export_report = subprocess.run(
                [str(nm), "--extern-only", "--defined-only", str(compat_bin)],
                capture_output=True, text=True, errors="replace", check=True).stdout
            exports = {line.split()[-1] for line in export_report.splitlines() if line.split()}
            required_exports = set(required_compat_routings) | {"_kUTTagClassMIMEType"}
            missing_exports = sorted(required_exports - exports)
            if missing_exports:
                raise RuntimeError(
                    f"Packaged FactorioCompat missing mandatory exports: {missing_exports}")
            print("macOS-only NSAppleEventManager and CGDisplay constant binds: FactorioCompat")
            print("Upstream framework routing confirmed: macOS Foundation/CoreGraphics and other shim providers -> FactorioCompat")
            print("Known missing compatibility symbol exported: _kUTTagClassMIMEType")
        return guest_sha, compat_sha


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inventory", action="store_true", help="Show bounded file/tool inventory, then exit")
    p.add_argument("--status", action="store_true", help="Read the last build stage and tail of its persistent log")
    p.add_argument("--audit-only", type=Path, metavar="EXISTING_IPA",
                   help="Run the current dependency audit against an existing private IPA without rebuilding")
    p.add_argument("--dmg", type=Path, help="Original Factorio 2.1.24 Mac DMG")
    p.add_argument("--template", type=Path, help="Reuse a successfully built game-free SDK 27.2 template instead of recompiling")
    p.add_argument("--seven-zip", type=Path, default=SEVEN_ZIP)
    args = p.parse_args()
    if args.status:
        return show_status()
    if args.audit_only is not None:
        ipa = args.audit_only.resolve()
        if not ipa.is_file():
            raise FileNotFoundError(f"Existing IPA not found: {ipa}")
        tag = "audit-existing-" + ipa.parent.name
        logfile = DIST / "build_private_duo_logs" / (tag + ".log")
        report_status("verify-existing-ipa", "running", tag, logfile, ipa=str(ipa))
        # Recheck embedded binary metadata, executable flags, and ZIP integrity;
        # do not touch FactorioData, original DMG, or a compiler.
        guest_sha, compat_sha = verify_output(ipa)
        print(f"Existing IPA: {ipa}", flush=True)
        print(f"IPA SHA-256: {sha256_file(ipa)}", flush=True)
        print(f"FactorioGuest SHA-256: {guest_sha}", flush=True)
        print(f"FactorioCompat SHA-256: {compat_sha}", flush=True)
        report_status("audit-existing-ipa", "running", tag, logfile, ipa=str(ipa))
        cmd = [sys.executable, "-u", str(ROOT / "Tools" / "audit_macho_imports.py"),
               "--ipa", str(ipa), "--report-dir", str(ipa.parent / "audit")]
        logfile.parent.mkdir(parents=True, exist_ok=True)
        with logfile.open("a", encoding="utf-8") as out:
            out.write(f"\n==== {datetime.now().isoformat()} {cmd!r} ====\n")
            out.flush()
            audit = subprocess.run(cmd, stdout=out, stderr=subprocess.STDOUT,
                                   text=True, errors="replace")
        print("Audit output recorded in:", logfile, flush=True)
        if audit.returncode:
            report_status("audit-existing-ipa", "failed", tag, logfile, ipa=str(ipa),
                          audit_exit_code=audit.returncode)
            return 2
        report_status("audit-existing-ipa", "completed", tag, logfile, ipa=str(ipa))
        print("Full host-side FactorioCompat reexport and native-framework import audit passed.", flush=True)
        print("This confirms no imports were left unverified by the audit; physical Duo launch remains untested.", flush=True)
        return 0
    dmgs = discover_dmgs()
    if args.inventory:
        describe_host(dmgs)
        return 0
    dmg = args.dmg
    if dmg is None:
        likely = [path for path in dmgs if "2.1.24" in path.name]
        if len(likely) == 1:
            dmg = likely[0]
        elif len(dmgs) == 1:
            dmg = dmgs[0]
        else:
            describe_host(dmgs)
            raise RuntimeError("Specify --dmg with an original Factorio 2.1.24 DMG; did not find one unambiguously")
    if not dmg.is_file():
        raise FileNotFoundError(f"Original DMG not found: {dmg}")
    if not args.seven_zip.is_file():
        raise FileNotFoundError(f"7-Zip not found: {args.seven_zip}")

    revision = run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"]).stdout.strip()
    branch = run(["git", "-C", str(ROOT), "branch", "--show-current"]).stdout.strip()
    if branch != "experiment/windows-native-ios27":
        raise RuntimeError(f"Wrong checkout branch: {branch}")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"ios27-routing-{timestamp}-{revision}"
    template = DIST / f"FactoriOS-template-{tag}.ipa"
    private = DIST / f"private-duo-{tag}"
    logfile = DIST / "build_private_duo_logs" / f"{tag}.log"
    print(f"Starting build; persistent log: {logfile}", flush=True)
    if args.template:
        template = args.template.resolve()
        if not template.is_file():
            raise FileNotFoundError(f"Existing template unavailable: {template}")
        with zipfile.ZipFile(template) as existing_template:
            if existing_template.testzip() is not None:
                raise RuntimeError("Existing template failed ZIP CRC check")
            names = existing_template.namelist()
            if not any(name.endswith("/FactorioPadTemplate.json") for name in names):
                raise RuntimeError("Existing template marker missing")
            if any("FactorioGuest.framework" in name or "/FactorioData/" in name for name in names):
                raise RuntimeError("Cannot reuse template containing private game assets")
        print(f"Reusing existing game-free template: {template}", flush=True)
        report_status("reuse-existing-template", "completed", tag, logfile, template=str(template))
    else:
        run_logged([sys.executable, str(ROOT / "Tools" / "build_windows_template.py"),
                    "--output", str(template)], "compile-and-template", tag, logfile)
    run_logged([sys.executable, str(ROOT / "Companion" / "package_ipa.py"),
                "dmg", str(template), str(dmg), str(private), str(args.seven_zip), "--no-data"],
               "repatch-guest-and-package-no-data", tag, logfile)
    ipa = private / "FactorioPad.ipa"
    report_status("validate-private-ipa", "running", tag, logfile, ipa=str(ipa))
    if not ipa.is_file() or (private / "FactorioData").exists():
        raise RuntimeError("Unexpected private build output; FactorioData must not be recreated")
    guest_sha, compat_sha = verify_output(ipa)
    report_status("validate-private-ipa", "completed", tag, logfile, ipa=str(ipa))
    print(f"Private IPA: {ipa}")
    print(f"IPA SHA-256: {sha256_file(ipa)}")
    print(f"FactorioGuest SHA-256: {guest_sha}")
    print(f"FactorioCompat SHA-256: {compat_sha}")
    print(f"Source: {revision}")
    print("FactorioData not accessed or regenerated.")

    print("Auditing the final, exact private IPA", flush=True)
    report_status("audit-private-ipa", "running", tag, logfile, ipa=str(ipa))
    audit = subprocess.run(
        [sys.executable, str(ROOT / "Tools" / "audit_macho_imports.py"),
         "--ipa", str(ipa), "--report-dir", str(private / "audit")],
        capture_output=True, text=True, errors="replace")
    (private / "audit-output.txt").write_text(
        audit.stdout + "\n" + audit.stderr, encoding="utf-8")
    with logfile.open("a", encoding="utf-8") as output:
        output.write("\n==== Final private IPA audit ====\n")
        output.write(audit.stdout + "\n" + audit.stderr + "\n")
    print(audit.stdout[-12000:], flush=True)
    if audit.stderr:
        print(audit.stderr[-4000:], file=sys.stderr, flush=True)
    if audit.returncode:
        print(f"BLOCKED: Audit returned {audit.returncode}. Private IPA is NOT ready for installation.",
              file=sys.stderr)
        print(f"Full audit: {private / 'audit-output.txt'}")
        report_status("audit-private-ipa", "failed", tag, logfile, ipa=str(ipa), audit_exit_code=audit.returncode)
        return 2
    report_status("audit-private-ipa", "completed", tag, logfile, ipa=str(ipa))
    print("Static audit passed. IPA remains unsigned: sign before installing.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError,
            zipfile.BadZipFile) as error:
        print(f"BUILD ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
