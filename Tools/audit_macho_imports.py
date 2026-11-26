#!/usr/bin/env python3
"""Audit private FactorioGuest Mach-O bindings without extracting FactorioData.

Run on Windows from any working directory:
    python F:/FactoriOS/Tools/audit_macho_imports.py

The script reads only two framework binaries from the existing private IPA.
Full tool output is saved under reports/macho-import-audit; the console is concise.
"""
from __future__ import annotations

import argparse
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ipa", type=pathlib.Path, default=DEFAULT_IPA)
    parser.add_argument("--llvm-bin", type=pathlib.Path, default=DEFAULT_LLVM)
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
        missing = sorted(required - exports)
        (args.report_dir / "missing-strong-compat-exports.txt").write_text(
            "\n".join(missing) + ("\n" if missing else ""), encoding="utf-8"
        )

        print(f"Private IPA: {args.ipa}")
        print(f"FactorioCompat defined externals: {len(exports)}")
        print(f"FactorioCompat strong/lazy guest bindings: {len(required)}")
        print(f"FactorioCompat weak guest bindings: {len(optional)}")
        print(f"Missing strong/lazy exports: {len(missing)}")
        for symbol in missing[:40]:
            print(f"  MISSING {symbol}")
        if len(missing) > 40:
            print(f"  ... {len(missing) - 40} more in report")
        if not required:
            print("WARNING: no FactorioCompat bindings were recognized; inspect the saved bind tables.")
            print(f"Reports: {args.report_dir}")
            return 2
        print(f"Reports: {args.report_dir}")
        return 1 if missing else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"AUDIT ERROR: {error}", file=sys.stderr)
        sys.exit(3)
