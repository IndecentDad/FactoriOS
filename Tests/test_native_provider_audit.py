#!/usr/bin/env python3
"""Game-free smoke tests for the real native iOS SDK providers in guest audit.

Run:
    python -m unittest discover -s Tests -p test_native_provider_audit.py

These tests validate provider parsing and linker selection, not SDK exports.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Tools"))
from audit_macho_imports import (
    PROVIDER_LINK_FLAGS, native_provider_from_line, provider_matches_binding,
)


class NativeProviderAuditTests(unittest.TestCase):
    def test_known_direct_native_provider_link_flags(self):
        expected = {
            "AVFoundation": ["-framework", "AVFoundation"],
            "CoreMedia": ["-framework", "CoreMedia"],
            "UniformTypeIdentifiers": ["-framework", "UniformTypeIdentifiers"],
            "libresolv": ["-lresolv"],
        }
        for provider, flags in expected.items():
            with self.subTest(provider=provider):
                self.assertEqual(PROVIDER_LINK_FLAGS[provider], flags)

    def test_unversioned_framework_provider_rows(self):
        rows = [
            ("AVFoundation", "AVFoundation", "_OBJC_CLASS_$_AVPlayer"),
            ("CoreMedia", "CoreMedia", "_CMSampleBufferGetImageBuffer"),
            ("UniformTypeIdentifiers", "UniformTypeIdentifiers", "_OBJC_CLASS_$_UTType"),
        ]
        for expected, provider, symbol in rows:
            with self.subTest(provider=provider):
                line = f"__DATA __got 0x00123456 pointer 0 {provider} {symbol}"
                self.assertEqual(native_provider_from_line(line), (expected, symbol))
                self.assertTrue(provider_matches_binding(expected, line))

    def test_framework_install_name_rows(self):
        for provider in ("AVFoundation", "CoreMedia", "UniformTypeIdentifiers"):
            line = (
                "segment offset bind 0 "
                f"/System/Library/Frameworks/{provider}.framework/{provider} _TestSymbol"
            )
            with self.subTest(provider=provider):
                self.assertEqual(native_provider_from_line(line), (provider, "_TestSymbol"))
                self.assertTrue(provider_matches_binding(provider, line))

    def test_versioned_resolver_dylib(self):
        for name in ("libresolv.9.dylib", "/usr/lib/libresolv.9.dylib", "libresolv.dylib"):
            line = f"__DATA __la_symbol_ptr 0x1 pointer 0 {name} _res_9_init"
            with self.subTest(name=name):
                self.assertEqual(native_provider_from_line(line), ("libresolv", "_res_9_init"))
                self.assertTrue(provider_matches_binding("libresolv", line))

    def test_dont_confuse_foundation_with_corefoundation(self):
        line = "__DATA __got 0x1 pointer 0 CoreFoundation _CFRelease"
        self.assertFalse(provider_matches_binding("Foundation", line))
        self.assertTrue(provider_matches_binding("CoreFoundation", line))


if __name__ == "__main__":
    unittest.main()
