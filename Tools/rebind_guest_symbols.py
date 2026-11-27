#!/usr/bin/env python3
"""Precisely route macOS-only guest imports to FactorioCompat without redirecting Foundation.

Rebinds library ordinals in Mach-O chained import tables or classic dyld bind
streams. Never rewrites an entire native Foundation dependency. Refuses to
silently proceed if a required symbol is absent, bound to an unexpected
library, or uses an unsupported layout.

This module is invoked by patch_factorio.py before the IPA is packaged.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

# symbol -> (original provider framework, desired provider framework)
REBINDS = {
    "_OBJC_CLASS_$_NSAppleEventManager": ("Foundation", "FactorioCompat"),
}
LC_SEGMENT_64 = 0x19
LC_DYLD_INFO = 0x22
LC_DYLD_CHAINED_FIXUPS = 0x80000034
DYLIB_CMDS = {0x0c, 0x18, 0x1f, 0x20, 0x23}
MAGIC_64 = 0xFEEDFACF


@dataclass
class LoadCommands:
    libraries: list[str]
    chained: tuple[int, int] | None
    dyld_info_command: int | None
    linkedit_command: int | None


def _read_name(data: bytes | bytearray, begin: int, end: int) -> str:
    if not (0 <= begin < end <= len(data)):
        raise ValueError("Invalid Mach-O name offset")
    stop = data.find(b"\0", begin, end)
    if stop < 0:
        raise ValueError("Unterminated Mach-O string")
    return bytes(data[begin:stop]).decode("utf-8", "strict")


def _load_commands(data: bytearray) -> LoadCommands:
    if len(data) < 32 or struct.unpack_from("<I", data)[0] != MAGIC_64:
        raise ValueError("Expected a thin little-endian Mach-O 64-bit binary")
    ncmds, sizeofcmds = struct.unpack_from("<II", data, 16)
    pos, end = 32, 32 + sizeofcmds
    if end > len(data):
        raise ValueError("Mach-O load commands exceed file bounds")
    libraries: list[str] = []
    chained = None
    info = None
    linkedit = None
    for _ in range(ncmds):
        if pos + 8 > end:
            raise ValueError("Truncated Mach-O load command")
        cmd, size = struct.unpack_from("<II", data, pos)
        if size < 8 or pos + size > end:
            raise ValueError("Malformed Mach-O load command size")
        if (cmd & 0x7fffffff) in DYLIB_CMDS:
            if size < 24:
                raise ValueError("Truncated dylib load command")
            offset = struct.unpack_from("<I", data, pos + 8)[0]
            if not 24 <= offset < size:
                raise ValueError("Invalid dylib load command name")
            libraries.append(_read_name(data, pos + offset, pos + size))
        if cmd == LC_DYLD_CHAINED_FIXUPS:
            if size < 16 or chained is not None:
                raise ValueError("Malformed or duplicate chained fixups command")
            chained = struct.unpack_from("<II", data, pos + 8)
        if (cmd & 0x7fffffff) == LC_DYLD_INFO:
            if size < 48 or info is not None:
                raise ValueError("Malformed or duplicate dyld info command")
            info = pos
        if cmd == LC_SEGMENT_64 and data[pos+8:pos+24].split(b"\0", 1)[0] == b"__LINKEDIT":
            if linkedit is not None or size < 72:
                raise ValueError("Malformed or duplicate __LINKEDIT segment")
            linkedit = pos
        pos += size
    if pos != end:
        raise ValueError("Malformed load-command ending")
    return LoadCommands(libraries, chained, info, linkedit)


def _framework(name: str) -> str:
    if "FactorioCompat.framework/FactorioCompat" in name:
        return "FactorioCompat"
    if "Foundation.framework/" in name:
        return "Foundation"
    return ""


def _resolve_ordinals(libraries: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for i, name in enumerate(libraries, 1):
        result.setdefault(_framework(name), i)
    if not result.get("Foundation") or not result.get("FactorioCompat"):
        raise ValueError(
            "Guest has no native Foundation and/or FactorioCompat library ordinal; "
            f"dependencies: {libraries}")
    return result


def _patch_chained_imports(data: bytearray, load: LoadCommands,
                           ordinals: dict[str, int]) -> dict[str, int]:
    assert load.chained is not None
    base, size = load.chained
    if base < 0 or size < 28 or base + size > len(data):
        raise ValueError("Malformed LC_DYLD_CHAINED_FIXUPS range")
    version, starts, imports, symbols, count, fmt, symbol_format = struct.unpack_from(
        "<7I", data, base)
    if version != 0 or symbol_format != 0:
        raise ValueError(f"Unsupported chained fixups version / symbol pool {version}/{symbol_format}")
    if fmt not in (1, 2, 3):
        raise ValueError(f"Unsupported chained import record format {fmt}")
    stride = {1: 4, 2: 8, 3: 16}[fmt]
    if not (28 <= imports < size and 28 <= symbols < size) or (
        count > (size - imports) // stride
    ):
        raise ValueError("Malformed chained import table")
    pool = base + symbols
    pool_end = base + size
    replacements = {name: 0 for name in REBINDS}
    for i in range(count):
        entry = base + imports + i * stride
        word = struct.unpack_from("<Q" if fmt == 3 else "<I", data, entry)[0]
        if fmt == 3:
            original_ord = word & 0xffff
            name_offset = (word >> 32) & 0xffffffff
            mask = 0xffff
        else:
            original_ord = word & 0xff
            name_offset = (word >> 9) & 0x7fffff
            mask = 0xff
        if name_offset >= pool_end - pool:
            raise ValueError("Chained import symbol pool offset outside range")
        symbol = _read_name(data, pool + name_offset, pool_end)
        if symbol not in REBINDS:
            continue
        original_provider, new_provider = REBINDS[symbol]
        original_expected = ordinals[original_provider]
        replacement = ordinals[new_provider]
        if replacement > mask:
            raise ValueError(f"{symbol}: new ordinal {replacement} exceeds chained field")
        if original_ord not in (original_expected, replacement):
            raise ValueError(
                f"{symbol}: original library ordinal {original_ord}, "
                f"expected {original_expected} ({original_provider})")
        if original_ord == replacement:
            raise ValueError(f"{symbol}: unexpected prepatched import")
        patched_word = (word & ~mask) | replacement
        struct.pack_into("<Q" if fmt == 3 else "<I", data, entry, patched_word)
        replacements[symbol] += 1
    return replacements


def _leb_end(blob: bytes, p: int) -> int:
    # For ULEB128/SLEB128 the continuation bit terminates both.
    for _ in range(11):
        if p >= len(blob):
            raise ValueError("Truncated dyld LEB128 operand")
        value = blob[p]
        p += 1
        if not (value & 0x80):
            return p
    raise ValueError("Invalid dyld LEB128 operand")


def _read_uleb(blob: bytes, begin: int, end: int) -> int:
    result = 0
    for i, value in enumerate(blob[begin:end]):
        result |= (value & 0x7f) << (7 * i)
    return result


def _write_uleb(value: int) -> bytes:
    if value < 0:
        raise ValueError("Negative dyld ordinal")
    result = bytearray()
    while True:
        b = value & 0x7f
        value >>= 7
        result.append(b | (0x80 if value else 0))
        if not value:
            return bytes(result)


def _set_ordinal(ordinal: int) -> bytes:
    return bytes([0x10 | ordinal]) if 0 <= ordinal <= 15 else b"\x20" + _write_uleb(ordinal)


def _rewrite_bind_stream(blob: bytes, ordinals: dict[str, int]) -> tuple[bytes, dict[str, int]]:
    out = bytearray()
    source_ordinal: int | None = None
    override: int | None = None
    replacements = {name: 0 for name in REBINDS}
    p = 0
    while p < len(blob):
        command_begin = p
        opcode = blob[p]
        p += 1
        kind, imm = opcode & 0xf0, opcode & 0x0f
        if kind == 0x00:  # DONE; also separates lazy-bind entries
            override = None
            source_ordinal = None
        elif kind == 0x10:
            source_ordinal = imm
            override = None
        elif kind == 0x20:
            end = _leb_end(blob, p)
            source_ordinal = _read_uleb(blob, p, end)
            override = None
            p = end
        elif kind == 0x30:
            source_ordinal = imm if imm == 0 else 0
            override = None
        elif kind == 0x40:
            end = blob.find(b"\0", p)
            if end < 0:
                raise ValueError("Unterminated dyld bind symbol")
            name = blob[p:end].decode("utf-8", "strict")
            if override is not None:
                if source_ordinal is None:
                    raise ValueError("No ordinal available to restore after targeted bind")
                out.extend(_set_ordinal(source_ordinal))
                override = None
            if name in REBINDS:
                from_name, to_name = REBINDS[name]
                if source_ordinal != ordinals[from_name]:
                    raise ValueError(
                        f"{name}: legacy bind ordinal {source_ordinal}; "
                        f"expected {ordinals[from_name]} ({from_name})")
                override = ordinals[to_name]
                out.extend(_set_ordinal(override))
                replacements[name] += 1
            p = end + 1
        elif kind in (0x60, 0x70, 0x80, 0xa0):
            p = _leb_end(blob, p)
        elif kind == 0xc0:
            p = _leb_end(blob, _leb_end(blob, p))
        elif kind in (0x50, 0x90, 0xb0):
            pass
        elif kind == 0xd0:
            # Threaded bind opcodes may carry a separate target table;
            # they require a different ordinal rebinding strategy.
            raise ValueError("Unsupported threaded dyld bind opcode; refuse to corrupt guest")
        else:
            raise ValueError(f"Unknown dyld bind opcode 0x{opcode:02x}")
        out.extend(blob[command_begin:p])
    return bytes(out), replacements


def _patch_classic(data: bytearray, load: LoadCommands,
                   ordinals: dict[str, int]) -> dict[str, int]:
    if load.dyld_info_command is None or load.linkedit_command is None:
        raise ValueError("Guest has neither chained import table nor classic dyld info")
    info = load.dyld_info_command
    # LC_DYLD_INFO(_ONLY) pairs: bind_off/size at +16/+20,
    # weak_bind_off/size at +24/+28, lazy_bind_off/size at +32/+36.
    replacements = {name: 0 for name in REBINDS}
    modified: list[tuple[int, bytes]] = []
    for rel in (16, 32):
        off, size = struct.unpack_from("<II", data, info + rel)
        if size == 0:
            continue
        if off < 0 or off + size > len(data):
            raise ValueError("Classic bind table outside guest file")
        rebuilt, count = _rewrite_bind_stream(bytes(data[off:off+size]), ordinals)
        for symbol, n in count.items():
            replacements[symbol] += n
        if rebuilt != data[off:off+size]:
            modified.append((rel, rebuilt))
    if not modified:
        return replacements

    seg = load.linkedit_command
    fileoff, filesize = struct.unpack_from("<QQ", data, seg + 40)
    if fileoff > len(data) or fileoff + filesize > len(data):
        raise ValueError("Malformed __LINKEDIT range")
    if fileoff + filesize < len(data):
        # Some signed binaries have a few trailing bytes after LINKEDIT.
        # New load info is appended; the segment must then encompass it.
        pass
    for rel, rebuilt in modified:
        while len(data) % 8:
            data.append(0)
        new_off = len(data)
        data.extend(rebuilt)
        if new_off > 0xffffffff or len(rebuilt) > 0xffffffff:
            raise ValueError("Dyld bind table offset exceeds uint32")
        struct.pack_into("<II", data, info + rel, new_off, len(rebuilt))
    new_filesize = len(data) - fileoff
    _, old_vmsize = struct.unpack_from("<QQ", data, seg + 24)
    new_vmsize = max(old_vmsize, (new_filesize + 0x3fff) & ~0x3fff)
    struct.pack_into("<Q", data, seg + 32, new_vmsize)
    struct.pack_into("<Q", data, seg + 48, new_filesize)
    return replacements


def rebind_macos_classes(data: bytearray) -> dict[str, int]:
    """Modify the bytearray or fail; callers should work on a throwaway copy."""
    load = _load_commands(data)
    ordinals = _resolve_ordinals(load.libraries)
    if load.chained is not None:
        modified = _patch_chained_imports(data, load, ordinals)
        mode = "chained imports"
    else:
        modified = _patch_classic(data, load, ordinals)
        mode = "classic dyld binds"
    absent = [symbol for symbol, count in modified.items() if count == 0]
    if absent:
        raise ValueError(
            f"Targeted macOS-only imports not found in {mode}: {absent}; "
            "verify the original guest format and exact symbol bindings")
    for symbol, count in modified.items():
        print(f"[patch] {mode}: {symbol}: redirected {count} Foundation "
              "bind(s) to FactorioCompat")
    return modified
