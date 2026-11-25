#!/usr/bin/env python3
"""Build and validate the game-free FactoriOS iOS template with Windows LLVM."""
from __future__ import annotations
import argparse, json, os, pathlib, plistlib, shutil, subprocess, sys, zipfile

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
              "Security", "IOKit", "AVFAudio"]


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
            "-lSystem", "-lobjc"]
    for name in FRAMEWORKS:
        args += ["-framework", name]
    run(args + ["-o", str(binary), *map(str, objects)])
    verify_macho(binary)
    verify_dependencies(binary)
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
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "dist" / "FactoriOS-template.ipa")
    args = parser.parse_args()
    actual = str(json.loads((SDK / "SDKSettings.json").read_text(encoding="utf-8")).get("Version", ""))
    if actual != SDK_VERSION:
        raise RuntimeError(f"expected SDK {SDK_VERSION}, found {actual} at {SDK}")
    if not all(p.exists() for p in (CLANG, CLANGXX, LD, READOBJ)):
        raise RuntimeError("LLVM 23 clang/clang++/ld64.lld/llvm-readobj are required")
    BUILD.mkdir(parents=True, exist_ok=True)
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
