#!/usr/bin/env python3
"""Guard the Windows-native build against repeating the upstream routing regression.

This test is game-free and runs on Windows:
  python -m unittest discover -s F:/FactoriOS/Tests -p test_upstream_framework_routing.py
"""
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tools"))
from patch_factorio import SHIM_FRAMEWORKS, COMPAT_PATH
from build_windows_template import FRAMEWORKS, REEXPORT_FRAMEWORKS

# Canonical macOS->iOS guest dependency routing, retained in upstream/main.
UPSTREAM_FRAMEWORKS = {
    "AppKit", "Cocoa", "Carbon", "ForceFeedback", "OpenGL", "OpenCL",
    "LDAP", "ApplicationServices", "Foundation", "CoreGraphics",
    "CoreVideo", "Metal", "CoreServices", "IOKit", "Security",
    "CoreAudio", "AudioToolbox",
}


class UpstreamFrameworkRoutingTests(unittest.TestCase):
    def test_guest_patcher_keeps_exact_upstream_framework_set(self):
        self.assertEqual(SHIM_FRAMEWORKS, UPSTREAM_FRAMEWORKS)
        self.assertEqual(COMPAT_PATH, "@rpath/FactorioCompat.framework/FactorioCompat")

    def test_windows_reexports_all_original_native_shim_providers(self):
        required = SHIM_FRAMEWORKS.intersection(FRAMEWORKS)
        self.assertFalse(required - REEXPORT_FRAMEWORKS,
                         f"Native guest imports hidden by FactorioCompat: {required - REEXPORT_FRAMEWORKS}")
        self.assertTrue({"Foundation", "CoreGraphics", "CoreVideo", "Metal",
                         "Security", "CoreAudio", "AudioToolbox", "IOKit"
                        }.issubset(REEXPORT_FRAMEWORKS))

    def test_windows_resolves_upstream_coreservices_exports(self):
        self.assertTrue(
            "CoreServices" in REEXPORT_FRAMEWORKS or
            "MobileCoreServices" in REEXPORT_FRAMEWORKS,
            "Legacy CoreServices UTType APIs need a compatible native iOS reexport"
        )

    def test_compat_link_matches_upstream_xcconfig_contract(self):
        source = (ROOT / "FactorioCompat.xcconfig").read_text(encoding="utf-8")
        upstream = set(re.findall(r"-reexport_framework,([A-Za-z0-9]+)", source))
        self.assertTrue(upstream)
        for framework in upstream - {"CoreServices"}:
            if framework in FRAMEWORKS:
                self.assertIn(framework, REEXPORT_FRAMEWORKS)
        self.assertIn("-reexport-lSystem", source)


if __name__ == "__main__":
    unittest.main()
