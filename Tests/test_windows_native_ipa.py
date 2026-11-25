#!/usr/bin/env python3
"""Validate a Windows-produced, game-free FactoriOS iOS SDK IPA."""
import argparse, pathlib, plistlib, subprocess, tempfile, zipfile, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Tools"))
from package_ipa import MARKER, app_prefix

def output(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def main():
    p=argparse.ArgumentParser();p.add_argument("ipa",type=pathlib.Path);p.add_argument("--llvm-bin",type=pathlib.Path,default=pathlib.Path(r"C:\Program Files\LLVM\bin"));p.add_argument("--sdk",default="27.2");a=p.parse_args()
    with zipfile.ZipFile(a.ipa) as z:
        assert z.testzip() is None, "ZIP CRC failure"
        prefix=app_prefix(z); names=set(z.namelist()); info=plistlib.loads(z.read(prefix+"Info.plist"))
        assert info.get("CFBundleIdentifier")=="pl.adrian.FactorioPad"
        assert info.get("CFBundleExecutable")=="FactorioPad"
        assert info.get("FactorioPadExternalDataVersion")==1
        assert info.get("UISupportedInterfaceOrientations")==["UIInterfaceOrientationLandscapeLeft","UIInterfaceOrientationLandscapeRight"]
        assert prefix+"FactoriOS-icon.png" in names
        assert json_marker(z.read(prefix+MARKER))
        assert not any("FactorioGuest.framework" in n or "/FactorioData/" in n for n in names)
        app=prefix+"FactorioPad"; fw=prefix+"Frameworks/FactorioCompat.framework/FactorioCompat"
        for n in (app,fw): assert (z.getinfo(n).external_attr>>16)&0o111, f"missing executable mode: {n}"
        with tempfile.TemporaryDirectory() as d:
            b=pathlib.Path(d);z.extract(app,b);z.extract(fw,b)
            for relative in (app,fw):
                details=output([str(a.llvm_bin/"llvm-readobj.exe"),"--file-headers","--macho-version-min",str(b/relative)])
                assert "Format: Mach-O arm64" in details and "Platform: ios" in details and f"SDK: {a.sdk}" in details,details
            deps=output([str(a.llvm_bin/"llvm-objdump.exe"),"--macho","--dylibs-used",str(b/app)])
            assert "@rpath/FactorioCompat.framework/FactorioCompat" in deps,deps
    print(f"Windows iOS SDK {a.sdk} IPA validation passed: arm64 app + compatibility framework; game-free.")

def json_marker(data):
    import json
    return json.loads(data)=={"format":2}
if __name__=="__main__": main()
