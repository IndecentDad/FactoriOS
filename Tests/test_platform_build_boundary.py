#!/usr/bin/env python3
"""Guard the production Swift iPad build from the separate Windows/UIKit shell.

Game-free:
    python -m unittest discover -s Tests -p test_platform_build_boundary.py

These are static build-boundary checks; a real Xcode/iPad build is still
needed to prove the original Swift target compiles and works.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = (ROOT / "FactorioPad.xcodeproj" / "project.pbxproj").read_text(encoding="utf-8")
BUILDER = (ROOT / "Tools" / "build_windows_template.py").read_text(encoding="utf-8")

WINDOWS_APP_ONLY = {
    "main.m", "FactorioUIKitApp.m", "FactorioTouchUIKit.m",
    "FactorioCursorView.m", "FactorioSaveSync.m",
    "FactorioTouchUIKit.h", "FactorioCursorView.h", "FactorioSaveSync.h",
}


class PlatformBuildBoundaryTests(unittest.TestCase):
    def test_original_xcode_target_remains_universal(self):
        self.assertIn('TARGETED_DEVICE_FAMILY = "1,2";', PROJECT)
        self.assertIn("INFOPLIST_KEY_UIRequiresFullScreen = NO;", PROJECT)
        self.assertIn("isa = PBXFileSystemSynchronizedRootGroup;", PROJECT)

    def test_xcode_swift_target_excludes_windows_only_app(self):
        matched = re.search(
            r'PBXFileSystemSynchronizedBuildFileExceptionSet;'
            r'\s*membershipExceptions = \((.*?)\);'
            r'\s*target = .*?/\* FactorioPad \*/;',
            PROJECT, re.DOTALL,
        )
        self.assertIsNotNone(matched, "Missing FactorioPad target folder exclusion")
        for filename in WINDOWS_APP_ONLY:
            with self.subTest(filename=filename):
                self.assertRegex(matched.group(1), r'(?m)^\s*' + re.escape(filename) + r',')
        self.assertIn("Info.plist,", matched.group(1))

    def test_windows_compiles_objc_shell_not_swift_app(self):
        self.assertIn('if suffix not in {".c", ".m", ".mm"}:', BUILDER)
        self.assertIn('list((ROOT / "FactorioPad").glob("*"))', BUILDER)
        self.assertTrue((ROOT / "FactorioPad" / "main.m").is_file())
        self.assertTrue((ROOT / "FactorioPad" / "FactorioUIKitApp.m").is_file())

    def test_windows_produces_native_universal_metadata(self):
        self.assertIn('"UIDeviceFamily": [1, 2]', BUILDER)
        self.assertIn('"UIRequiresFullScreen": False', BUILDER)
        self.assertIn('info["UISupportedInterfaceOrientations~ipad"]', BUILDER)


if __name__ == "__main__":
    unittest.main()
