#!/usr/bin/env python3
"""Build and validate the game-free FactoriOS iOS template with Windows LLVM."""
from __future__ import annotations
import argparse, json, os, pathlib, plistlib, shutil, struct, subprocess, sys, zipfile
from datetime import datetime, timezone
from patch_factorio import SHIM_FRAMEWORKS

ROOT = pathlib.Path(__file__).resolve().parents[1]
SDK = pathlib.Path(os.environ.get("FACTORIOS_IOS_SDK", r"F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk"))
BUILD = pathlib.Path(os.environ.get("FACTORIOS_BUILD_DIR", r"F:\NXNative\Builds\FactoriOS-ios27"))
MIN_IOS = os.environ.get("FACTORIOS_MIN_IOS", "17.0")
SDK_VERSION = "27.2"
LLVM = pathlib.Path(os.environ.get("LLVM_BIN", r"C:\Program Files\LLVM\bin"))
CLANG, CLANGXX = LLVM / "clang.exe", LLVM / "clang++.exe"
LD, READOBJ = LLVM / "ld64.lld.exe", LLVM / "llvm-readobj.exe"
FRAMEWORKS = ["Foundation", "UIKit", "QuartzCore", "CoreGraphics", "CoreFoundation",
              "GameController", "Metal", "AudioToolbox", "CoreAudio", "CoreVideo",
              "Security", "IOKit", "MobileCoreServices", "AVFAudio"]
# Keep the original upstream patcher's two-level dylib routing intact:
# every native iOS framework whose macOS name is rewritten to FactorioCompat
# MUST be reexported by FactorioCompat, unless the shim implements the export.
# CoreServices is macOS-only; MobileCoreServices supplies its legacy UTType APIs.
REEXPORT_FRAMEWORKS = set(FRAMEWORKS).intersection(SHIM_FRAMEWORKS) | {"MobileCoreServices"}


def run(args: list[str], quiet: bool = False) -> str:
    if not quiet:
        print("+", subprocess.list2cmdline(args))
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {subprocess.list2cmdline(args)}\n{result.stdout}")
    if result.stdout and not quiet:
        print(result.stdout, end="")
    return result.stdout


def verify_macho(binary: pathlib.Path) -> None:
    details = run([str(READOBJ), "--file-headers", "--macho-version-min", str(binary)], quiet=True)
    required = ("Format: Mach-O arm64", "Platform: ios", f"SDK: {SDK_VERSION}")
    missing = [item for item in required if item not in details]
    if missing:
        raise RuntimeError(f"{binary} failed Mach-O validation; missing {missing}:\n{details}")
    print(f"validated {binary.name}: arm64 / iOS / SDK {SDK_VERSION}")


def verify_dependencies(binary: pathlib.Path, expected: str | None = None) -> None:
    details = run([str(LLVM / "llvm-objdump.exe"), "--macho", "--dylibs-used", str(binary)], quiet=True)
    if expected and expected not in details:
        raise RuntimeError(f"{binary.name} does not link {expected}:\n{details}")
    if "FactorioGuest" in details:
        raise RuntimeError(f"game guest was unexpectedly linked into {binary.name}")


def verify_compat_runtime_exports(binary: pathlib.Path) -> None:
    """Fail before packaging if required runtime globals or IOKit reexport are absent."""
    nm = LLVM / "llvm-nm.exe"
    exports = run([str(nm), "--extern-only", "--defined-only", str(binary)], quiet=True)
    public = {line.split()[-1] for line in exports.splitlines() if line.split()}
    required = {
        "_kUTTagClassMIMEType",
        "_kUTTypeUTF8PlainText",
        "_OBJC_CLASS_$_NSColor",
        "_OBJC_CLASS_$_NSAppleEventManager",
        "_kCGDisplayShowDuplicateLowResolutionModes",
    }
    missing = sorted(required - public)
    if missing:
        raise RuntimeError(f"FactorioCompat required runtime exports absent: {missing}")

    raw = binary.read_bytes()
    if len(raw) < 32 or struct.unpack_from("<I", raw)[0] != 0xFEEDFACF:
        raise RuntimeError("Expected a thin 64-bit FactorioCompat Mach-O")
    ncmds, sizeofcmds = struct.unpack_from("<II", raw, 16)
    pos, end = 32, 32 + sizeofcmds
    reexports = []
    ordinary_loads = []
    for _ in range(ncmds):
        if pos + 8 > min(len(raw), end):
            raise RuntimeError("Malformed FactorioCompat load command")
        cmd, length = struct.unpack_from("<II", raw, pos)
        if length < 8 or pos + length > min(len(raw), end):
            raise RuntimeError("Malformed FactorioCompat load command length")
        if cmd in (0x8000001F, 0x0C, 0x80000018):  # reexport, load, weak-load
            offset = struct.unpack_from("<I", raw, pos + 8)[0]
            if not 24 <= offset < length:
                raise RuntimeError(f"Malformed framework path in load command 0x{cmd:x}")
            framework_path = raw[pos+offset:pos+length].split(b"\0", 1)[0].decode("utf-8")
            if cmd == 0x8000001F:
                reexports.append(framework_path)
            else:
                ordinary_loads.append(framework_path)
        pos += length
    if pos != end:
        raise RuntimeError("Malformed FactorioCompat load commands end")
    # Native frameworks must be genuine LC_REEXPORT_DYLIB commands.
    # Ordinary LC_LOAD_DYLIB commands DO NOT make native iOS imports available
    # to FactorioGuest when their original framework ordinal was rewritten
    # to FactorioCompat by the upstream Mach-O guest patcher.
    def is_framework_reexport(path: str, framework: str) -> bool:
        parts = path.replace("\\\\", "/").split("/")
        if len(parts) >= 2 and parts[-2:] == [framework + ".framework", framework]:
            return True
        return (len(parts) >= 4 and
                parts[-4:] == [framework + ".framework", "Versions",
                               parts[-2], framework] and bool(parts[-2]))

    def is_libsystem(path: str) -> bool:
        return path.endswith("/libSystem.B.dylib") or path.endswith("/libSystem.dylib")

    providers = {
        framework: any(is_framework_reexport(path, framework) for path in reexports)
        for framework in sorted(REEXPORT_FRAMEWORKS)
    }
    providers["libSystem"] = any(is_libsystem(path) for path in reexports)
    missing_providers = [name for name, present in providers.items() if not present]
    if missing_providers:
        raise RuntimeError(
            f"Upstream guest routing requires missing native LC_REEXPORT_DYLIB providers: "
            f"{missing_providers}; actual reexports: {reexports}; "
            f"ordinary/weak loads: {ordinary_loads}")

    print("validated FactorioCompat exports: NSColor, AppleEventManager, CoreGraphics and UTType globals")
    print("validated upstream-compatible native LC_REEXPORT_DYLIB providers: "
          + ", ".join(reexports))


def compile_sources(sources: list[pathlib.Path], output: pathlib.Path, cache: pathlib.Path) -> list[pathlib.Path]:
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    objects = []
    for source in sorted(sources):
        suffix = source.suffix.lower()
        if suffix not in {".c", ".m", ".mm"}:
            continue
        obj = output / (source.stem + ".o")
        compiler = CLANGXX if suffix == ".mm" else CLANG
        cmd = [str(compiler), "-target", f"arm64-apple-ios{MIN_IOS}", "-isysroot", str(SDK),
               "-fblocks", "-O2", "-fvisibility=default", "-I", str(ROOT / "FactorioCompat"),
               "-I", str(ROOT / "FactorioPad"), "-c", str(source), "-o", str(obj)]
        if suffix in {".m", ".mm"}:
            cmd += ["-fobjc-arc", f"-fobjc-runtime=ios-{MIN_IOS}"]
        if suffix != ".mm":
            cmd += ["-fmodules", "-fmodules-cache-path=" + str(cache)]
        else:
            # LLVM 23 Windows imports incomplete Foundation declarations for ObjC++ modules.
            cmd += ["-fno-modules", "-std=c++20"]
        run(cmd, quiet=True)
        objects.append(obj)
        print(f"compiled {source.relative_to(ROOT)}")
    if not objects:
        raise RuntimeError("no C/Objective-C sources found")
    return objects


def build_compat() -> pathlib.Path:
    objects = compile_sources(list((ROOT / "FactorioCompat").glob("*")),
                              BUILD / "Objects" / "FactorioCompat", BUILD / "ModuleCache")
    framework = BUILD / "Product" / "FactorioCompat.framework"
    framework.mkdir(parents=True, exist_ok=True)
    binary = framework / "FactorioCompat"
    args = [str(LD), "-dylib", "-arch", "arm64", "-platform_version", "ios", MIN_IOS, SDK_VERSION,
            "-syslibroot", str(SDK), "-install_name", "@rpath/FactorioCompat.framework/FactorioCompat",
            "-current_version", "2.3.0", "-compatibility_version", "1.0", "-undefined", "error",
            "-reexport-lSystem", "-lobjc"]
    for name in FRAMEWORKS:
        # The upstream Factorio guest patcher rebinds macOS Foundation,
        # CoreGraphics, CoreVideo, Metal, Security, CoreAudio, AudioToolbox
        # and IOKit libraries to FactorioCompat. Those native iOS symbols
        # must be visible through true reexports, while macOS-only symbols
        # remain implemented by local compatibility shims.
        option = "-reexport_framework" if name in REEXPORT_FRAMEWORKS else "-framework"
        args += [option, name]
    run(args + ["-o", str(binary), *map(str, objects)])
    verify_macho(binary)
    verify_dependencies(binary)
    verify_compat_runtime_exports(binary)
    info = {"CFBundleExecutable": "FactorioCompat", "CFBundleIdentifier": "pl.adrian.FactorioCompat",
            "CFBundleName": "FactorioCompat", "CFBundlePackageType": "FMWK",
            "CFBundleInfoDictionaryVersion": "6.0", "CFBundleShortVersionString": "2.3.0",
            "CFBundleVersion": "1", "MinimumOSVersion": MIN_IOS}
    (framework / "Info.plist").write_bytes(plistlib.dumps(info, sort_keys=True))
    return framework


def build_app() -> tuple[pathlib.Path, pathlib.Path]:
    framework = BUILD / "Product" / "FactorioCompat.framework"
    objects = compile_sources(list((ROOT / "FactorioPad").glob("*")),
                              BUILD / "Objects" / "FactorioPad", BUILD / "ModuleCache")
    binary = BUILD / "Product" / "FactorioPad"
    args = [str(LD), "-arch", "arm64", "-platform_version", "ios", MIN_IOS, SDK_VERSION,
            "-syslibroot", str(SDK), "-e", "_main", "-lSystem", "-lobjc", "-lc++",
            "-F", str(framework.parent), "-framework", "FactorioCompat",
            "-rpath", "@executable_path/Frameworks"]
    for name in FRAMEWORKS:
        args += ["-framework", name]
    run(args + ["-o", str(binary), *map(str, objects)])
    verify_macho(binary)
    verify_dependencies(binary, "@rpath/FactorioCompat.framework/FactorioCompat")
    return binary, framework


def package_template(binary: pathlib.Path, framework: pathlib.Path, output: pathlib.Path) -> None:
    payload = BUILD / "Payload"
    if payload.exists():
        shutil.rmtree(payload)
    app = payload / "FactorioPad.app"
    (app / "Frameworks").mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, app / "FactorioPad")
    shutil.copytree(framework, app / "Frameworks" / "FactorioCompat.framework", dirs_exist_ok=True)
    info = plistlib.loads((ROOT / "FactorioPad" / "Info.plist").read_bytes())
    info.update({"CFBundleExecutable": "FactorioPad", "CFBundleIdentifier": "pl.adrian.FactorioPad",
                 "CFBundleName": "FactoriOS", "CFBundleDisplayName": "FactoriOS",
                 "CFBundlePackageType": "APPL", "CFBundleInfoDictionaryVersion": "6.0",
                 "CFBundleShortVersionString": "2.3.0", "CFBundleVersion": "1",
                 "FactoriOSSourceCommit": run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], quiet=True).strip(),
                 "FactoriOSBuildUTC": datetime.now(timezone.utc).isoformat(),
                 "FactoriOSTargetSDK": SDK_VERSION,
                 "MinimumOSVersion": MIN_IOS, "FactorioPadExternalDataVersion": 1,
                 "CFBundleSupportedPlatforms": ["iPhoneOS"], "LSRequiresIPhoneOS": True})
    icon = BUILD / "FactoriOS-icon.png"
    from PIL import Image
    Image.open(ROOT / "Branding" / "icon.png").convert("RGB").resize((1024, 1024), Image.Resampling.LANCZOS).save(icon)
    shutil.copy2(icon, app / "FactoriOS-icon.png")
    info["CFBundleIcons"] = {"CFBundlePrimaryIcon": {"CFBundleIconFiles": ["FactoriOS-icon"]}}
    info["CFBundleIcons~ipad"] = info["CFBundleIcons"]
    info["UISupportedInterfaceOrientations"] = ["UIInterfaceOrientationLandscapeLeft", "UIInterfaceOrientationLandscapeRight"]
    info["UISupportedInterfaceOrientations~ipad"] = info["UISupportedInterfaceOrientations"]
    (app / "Info.plist").write_bytes(plistlib.dumps(info, sort_keys=True))
    raw = BUILD / "FactorioPad-unsigned.ipa"
    with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted((BUILD / "Payload").rglob("*")):
            if path.is_file():
                name = path.relative_to(BUILD).as_posix()
                entry = zipfile.ZipInfo.from_file(path, name)
                if path.name in {"FactorioPad", "FactorioCompat"}:
                    entry.create_system = 3
                    entry.external_attr = (0o100755 << 16)
                archive.writestr(entry, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing template: {output}")
    run([sys.executable, str(ROOT / "Tools" / "package_ipa.py"), "template", str(raw), str(output)])
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("template IPA failed ZIP integrity check")
        names = archive.namelist()
        if any("FactorioGuest.framework" in n or "/FactorioData/" in n for n in names):
            raise RuntimeError("game files found in public template")
        if len([n for n in names if n.endswith("/FactorioPadTemplate.json")]) != 1:
            raise RuntimeError("template marker missing or duplicated")
        prefix = "Payload/FactorioPad.app/"
        info = plistlib.loads(archive.read(prefix + "Info.plist"))
        if info.get("CFBundleExecutable") != "FactorioPad" or info.get("CFBundleIdentifier") != "pl.adrian.FactorioPad":
            raise RuntimeError("app metadata is incomplete")
        if prefix + "FactoriOS-icon.png" not in names:
            raise RuntimeError("FactoriOS icon is missing")
        for path in (prefix + "FactorioPad", prefix + "Frameworks/FactorioCompat.framework/FactorioCompat"):
            entry = archive.getinfo(path)
            if (entry.external_attr >> 16) & 0o111 == 0:
                raise RuntimeError(f"executable permission missing in IPA: {path}")
    print(f"template created: {output} ({output.stat().st_size:,} bytes)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat-only", action="store_true")
    parser.add_argument("--verify-existing-compat", action="store_true", help="Validate the already linked FactorioCompat binary without recompiling")
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "dist" / "FactoriOS-template.ipa")
    args = parser.parse_args()
    actual = str(json.loads((SDK / "SDKSettings.json").read_text(encoding="utf-8")).get("Version", ""))
    if actual != SDK_VERSION:
        raise RuntimeError(f"expected SDK {SDK_VERSION}, found {actual} at {SDK}")
    if not all(p.exists() for p in (CLANG, CLANGXX, LD, READOBJ)):
        raise RuntimeError("LLVM 23 clang/clang++/ld64.lld/llvm-readobj are required")
    BUILD.mkdir(parents=True, exist_ok=True)
    if args.verify_existing_compat:
        binary = BUILD / "Product" / "FactorioCompat.framework" / "FactorioCompat"
        if not binary.is_file():
            raise FileNotFoundError(f"No existing compiled compatibility binary: {binary}")
        verify_macho(binary)
        verify_dependencies(binary)
        verify_compat_runtime_exports(binary)
        print(f"Verified existing FactorioCompat without recompiling: {binary}")
        return 0
    framework = build_compat()
    if not args.compat_only:
        binary, framework = build_app()
        package_template(binary, framework, args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
