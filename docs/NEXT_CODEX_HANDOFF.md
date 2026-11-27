# FactoriOS Windows SDK 27.2 — Finish existing IPA audit status, then device test

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

## CURRENT STATUS — audit clean by counts, process exit not yet confirmed

The following existing IPA was rebuilt from the original owned Factorio
2.1.24 DMG with the restored upstream routing:

  F:\FactoriOS\dist\private-duo-ios27-routing-20261126-204853-2b75de1\FactorioPad.ipa

SHA-256: f74007552be18f9fa1fe795ba2b40d1e87136bc31d6ba92e24243a4d077549d9

Latest audit evidence reports all 160 missing direct FactorioCompat exports
verified by iOS-arm64 reexport linker probes. The latest report has zero
unverified FactorioCompat imports AND zero unverified native-framework imports.
The new native-provider regression suite passed 5/5.

The status JSON still said "failed" because it reflected an older run.
Source now fixes status transitions: prior exit_code/audit_exit_code/error
fields cannot be inherited from an earlier attempt with the same tag.
The --audit-only entrypoint now writes audit-latest-output.txt and
audit-latest-result.json with the exact IPA SHA-256 and actual subprocess
exit code of the *current* invocation; older appended logs are not evidence
of the most recent status.

## NEXT STEPS — autonomously finish, no rebuilt IPA unless justified

1. Pull latest experiment branch. Do not touch main, stable release,
   FactorioData or saves.
2. Run the game-free status regression tests:
   python -m unittest discover -s F:/FactoriOS/Tests -p test_private_audit_status.py
3. Run the exact existing-IPA audit **through the status-aware wrapper**:
   python -u F:/FactoriOS/Tools/build_private_duo.py --audit-only "F:/FactoriOS/dist/private-duo-ios27-routing-20261126-204853-2b75de1/FactorioPad.ipa"
4. Read the process exit code, the new audit-latest-result.json, and the
   build_private_duo_status.json. Require an actual exit code of zero and
   a matching IPA SHA256. If exit is nonzero even with zero unverified
   provider imports, inspect other audit gates (invalid_known, no required
   imports, exceptions), fix the actual bug, rerun, commit and push.
5. If and only if the completed run returns zero and verifies the same
   IPA hash, report the existing IPA as host-audit-validated and ready for
   the next **physical** iPhone Duo test. This is not proof the game starts.
6. Do not rebuild the IPA for audit-only changes. No reason to rebuild
   unless the packaged app/guest/compat code actually changes.

Commit/push any remaining code fixes. Do not end the turn at another
status check or before interpreting the saved current-run result.
