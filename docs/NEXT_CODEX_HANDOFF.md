# FactoriOS Windows SDK 27.2 — Resume from upstream routing restoration

## ACTIVE TASK — do not stop after diagnosing

Read root AGENTS.md. Continue implementing, testing and committing/pushing
routine fixes autonomously in experiment/windows-native-ios27. No changes to
main, stable releases, proprietary Factorio data, or user saves.

The previous Windows experiment was **not** a minimal Duo-screen patch.
It rewrote upstream Tools/patch_factorio.py to keep seven macOS frameworks
as native iOS dependencies. The original Xcode build instead redirects their
FactorioGuest Mach-O library ordinals to FactorioCompat and reexports native
APIs through FactorioCompat. This is why repeated device builds failed on
macOS-only symbols from native Foundation and CoreGraphics.

## Verified root-cause evidence

- Upstream MyNameIsArko/FactorioPad and IndecentDad/FactoriOS main have an
  identical Tools/patch_factorio.py (Git blob 58bfe0afd0aaebdce60aac83a4c9b65ad12d710e).
- The upstream SHIM_FRAMEWORKS set includes Foundation, CoreGraphics,
  CoreVideo, Metal, CoreServices, IOKit, Security, CoreAudio, AudioToolbox
  alongside the macOS-only frameworks.
- Original FactorioCompat.xcconfig explicitly passes -reexport_framework
  for those providers, as well as -reexport-lSystem.
- Windows experiment previously removed Foundation, CoreGraphics, CoreVideo,
  Metal, Security, CoreAudio, AudioToolbox from SHIM_FRAMEWORKS and only
  reexported a few frameworks. Its specialized per-symbol fixes and narrower
  audits hid rather than solved this mismatch.
- Device logs confirmed FactorioGuest failed on a native Foundation
  NSAppleEventManager import, then on a native CoreGraphics
  kCGDisplayShowDuplicateLowResolutionModes import. Both are already
  implemented by the existing FactorioCompat code.
- The afccbc9 IPA was never cleared by the expanded native audit, which
  Codex failed to inspect. The newest device logs and build identity show
  it progressed past the first bad binding but failed on the second.
- The private FactorioGuest version embedded in the package was verified
  as 2.1.24. No evidence currently suggests an executable/GameData version
  mismatch as the cause.

## Source changes now committed (pull latest, don't rely on afccbc9)

1. Restored Tools/patch_factorio.py **byte-for-byte from main/upstream**.
   It no longer calls a separate targeted rebinder.
2. Deleted obsolete Tools/rebind_guest_symbols.py and its synthetic tests.
3. Tools/build_windows_template.py derives REEXPORT_FRAMEWORKS from the
   restored patcher's SHIM_FRAMEWORKS and reexports all native SDK
   providers that the original patcher rewrites. It also reexports
   MobileCoreServices for legacy UTType C functions, and uses CoreServices
   when the extracted SDK contains a linkable stub.
4. Tools/build_windows_template.py preflights the actual LC_REEXPORT_DYLIB
   commands for the entire set of required native providers.
5. Tools/build_private_duo.py now validates **upstream routing** (guest loads
   FactorioCompat, not native Foundation/CoreGraphics/etc.), retaining
   symbol-specific protection for the two observed device failures.
6. Tools/audit_macho_imports.py now probes the expanded original reexport
   set, not only IOKit, MobileCoreServices and libSystem.
7. Tests/test_upstream_framework_routing.py guards this behavior against
   accidental reversal in a later experiment.

## NEXT STEPS, autonomous

1. git -C F:/FactoriOS pull --ff-only
2. Ensure branch is experiment/windows-native-ios27; do not reset or alter
   main or any other checkout.
3. Run:
   python -m unittest discover -s F:/FactoriOS/Tests -p test_upstream_framework_routing.py
4. Read full previous failed audit results in:
   F:/FactoriOS/dist/private-duo-ios27-routing-20261126-194941-afccbc9/audit/
   and its persistent build log. Distinguish genuine SDK missing exports from
   obsolete native routing in that IPA.
5. Build fresh Windows SDK 27.2 template and private IPA using:
   python -u F:/FactoriOS/Tools/build_private_duo.py --dmg F:/FactoriOS/factorio_mac_2.1.24.dmg
   The guest must be repatched from the original DMG to recover the original
   upstream library ordinals. Do NOT reuse the last IPA or old patched guest.
6. Inspect complete host audit and validate all guest import providers,
   including upstream CoreServices alias/reexport expectations.
7. Fix real validation and linker issues yourself; do not disable checks or
   invent stub implementations. Push source changes after fixes.
8. Report exact commit, resulting IPA SHA-256, original game guest version,
   verified source/SDK metadata, full audit counts and any remaining gaps.
   The next install on the physical Duo is needed to prove runtime launch.

Never describe host-side checks as device-launch proof. The final criterion is
that FactorioGuest actually loads and Factorio runs on iPhone Duo, with the
display changes tested afterward. No further per-symbol guess/rebuild cycle.
