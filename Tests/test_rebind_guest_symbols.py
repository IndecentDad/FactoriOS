#!/usr/bin/env python3
"""Regression fixtures for selective Mach-O Foundation class rebinding.

Run without the Factorio DMG:
  python -m unittest discover -s Tests -p test_rebind_guest_symbols.py
"""
from __future__ import annotations

import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "Tools"))
from rebind_guest_symbols import rebind_macos_classes

SYMBOL = b"_OBJC_CLASS_$_NSAppleEventManager"


def pad(data: bytes, alignment: int = 8) -> bytes:
    return data + b"\0" * (-len(data) % alignment)


def dylib(name: str) -> bytes:
    raw = name.encode() + b"\0"
    command_size = 24 + len(pad(raw))
    return struct.pack("<6I", 0x0c, command_size, 24, 0, 0, 0) + pad(raw)


def header(commands: list[bytes]) -> bytearray:
    header = bytearray(32)
    struct.pack_into("<8I", header, 0, 0xFEEDFACF, 0x0100000C,
                     0, 6, len(commands), sum(map(len, commands)), 0, 0)
    return header + bytearray(b"".join(commands))


def libs() -> list[bytes]:
    return [
        dylib("/System/Library/Frameworks/Foundation.framework/Foundation"),
        dylib("@rpath/FactorioCompat.framework/FactorioCompat"),
    ]


def chained_fixture(fmt: int = 1, wrong_provider: bool = False,
                    missing_target: bool = False,
                    corefoundation_first: bool = False) -> bytearray:
    name = (b"_OBJC_CLASS_$_OtherClass" if missing_target else SYMBOL) + b"\0"
    stride = {1: 4, 2: 8, 3: 16}[fmt]
    blob = bytearray(28 + stride + len(name))
    struct.pack_into("<7I", blob, 0, 0, 0, 28, 28 + stride, 1, fmt, 0)
    provider = 3 if wrong_provider else (2 if corefoundation_first else 1)
    if fmt == 3:
        struct.pack_into("<Qq", blob, 28, provider, -123)
    else:
        struct.pack_into("<I", blob, 28, provider)
        if fmt == 2:
            struct.pack_into("<i", blob, 32, -123)
    blob[28+stride:] = name
    commands = libs()
    if corefoundation_first:
        commands.insert(0, dylib(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"))
    cmd_start = 32 + sum(map(len, commands)) + 16
    commands.append(struct.pack("<4I", 0x80000034, 16, cmd_start, len(blob)))
    return header(commands) + blob


def classic_fixture() -> bytearray:
    stream = (b"\x11\x40" + SYMBOL + b"\0\x90"
              + b"\x40_NSLog\0\x90\x00")
    commands = libs()
    segment = bytearray(72)
    struct.pack_into("<II", segment, 0, 0x19, 72)
    segment[8:18] = b"__LINKEDIT"
    commands.append(segment)
    info = bytearray(48)
    struct.pack_into("<II", info, 0, 0x80000022, 48)
    commands.append(info)
    prefix = header(commands)
    end = len(prefix)
    linkedit_offset = 32 + sum(map(len, commands[:2]))
    dyld_offset = linkedit_offset + 72
    struct.pack_into("<QQ", prefix, linkedit_offset + 40, end, len(stream))
    struct.pack_into("<Q", prefix, linkedit_offset + 32, 0x4000)
    struct.pack_into("<II", prefix, dyld_offset + 16, end, len(stream))
    return prefix + stream


class RebindTests(unittest.TestCase):
    def test_chained_short_import(self):
        data = chained_fixture(1)
        before = data[:]
        report = rebind_macos_classes(data)
        self.assertEqual(report, {SYMBOL.decode(): 1})
        command_offset = 32 + sum(map(len, libs()))
        payload_offset = struct.unpack_from("<I", before, command_offset + 8)[0]
        entry = payload_offset + 28
        self.assertEqual(data[entry], 2)
        self.assertEqual(data[entry+1:], before[entry+1:])

    def test_corefoundation_does_not_alias_foundation(self):
        data = chained_fixture(corefoundation_first=True)
        original = data[:]
        rebind_macos_classes(data)
        changes = [(i, old, new) for i, (old, new)
                   in enumerate(zip(original, data)) if old != new]
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0][1:], (2, 3))

    def test_chained_addend_import(self):
        data = chained_fixture(2)
        before = data[:]
        rebind_macos_classes(data)
        changed = [i for i, (a, b) in enumerate(zip(before, data)) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertEqual(data[changed[0]], 2)

    def test_chained_wide_import(self):
        data = chained_fixture(3)
        before = data[:]
        rebind_macos_classes(data)
        changed = [i for i, (a, b) in enumerate(zip(before, data)) if a != b]
        self.assertEqual(len(changed), 1)
        self.assertEqual(data[changed[0]], 2)

    def test_unexpected_ordinal_rejected(self):
        with self.assertRaisesRegex(ValueError, "original library ordinal"):
            rebind_macos_classes(chained_fixture(wrong_provider=True))

    def test_missing_required_import_rejected(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            rebind_macos_classes(chained_fixture(missing_target=True))

    def test_classic_bind_restores_foundation_for_next_symbol(self):
        data = classic_fixture()
        old_len = len(data)
        rebind_macos_classes(data)
        commands = libs()
        info_off = 32 + sum(map(len, commands)) + 72
        new_off, new_size = struct.unpack_from("<II", data, info_off+16)
        stream = bytes(data[new_off:new_off+new_size])
        self.assertGreater(len(data), old_len)
        self.assertIn(b"\x12\x40" + SYMBOL + b"\0\x90\x11\x40_NSLog\0", stream)
        self.assertEqual(stream[-1], 0)
        self.assertEqual(len(data), new_off + new_size)


if __name__ == "__main__":
    unittest.main()
