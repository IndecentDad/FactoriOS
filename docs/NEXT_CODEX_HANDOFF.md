# Next Codex Session — FactoriOS Windows-Native Runtime Recovery

## Mandatory instructions

Read the root AGENTS.md first and follow it. This handoff supersedes older
instructions to "wait for the user's next instruction." The active task is
**resolve the actual iPhone Duo launch failure and get Factorio 2.1.24 running**,
not just compile/package an IPA. Continue autonomously within the boundaries
authorized in AGENTS.md. Preserve main, stable releases, game data, and saves.

**Do not stop and return an investigation-only status message for ordinary
compiler errors, code differences, linker failures, or test failures.**

## Source and build

- Source checkout: F:\FactoriOS
- Branch: experiment/windows-native-ios27
- Original owned game DMG: F:\FactoriOS\factorio_mac_2.1.24.dmg
- iOS: target iPhone Duo, iPhoneOS SDK 27.2, native Windows LLVM/ld64.lld.
- Private IPA baseline (source 9f671ccd):
  F:\FactoriOS\dist\private-duo-ios27-routing-20261126-192849-9f671cc\FactorioPad.ipa
- This candidate's SHA-256:
  b03299cb1d8b2f2223b318966d5f8c5c252bf534b1300dca124784d8e1fecbc9
- Previous reports show a 169-binding **FactorioCompat-scoped** static audit
  passing with zero unresolved direct/reexport strong imports. This does not
  prove actual dyld launch, whole Mach-O dependency graph, package installation,
  or gameplay.

## New evidence and immediate work

## Fifth-build priority: confirmed newer iPhone Duo log

The user supplied FactorioPad(20261127-015510).log. Its newest startup
is 2026-11-27 01:52:43 UTC and proves source afccbc9a... from the embedded
build stamp, rather than a stale IPA. The real dlopen failure in THAT build:
  Symbol not found: _kCGDisplayShowDuplicateLowResolutionModes
  Referenced from: FactorioGuest
  Expected in: /System/Library/Frameworks/CoreGraphics.framework/CoreGraphics

This is distinct from the earlier NSAppleEventManager failure, which the
afccbc9 package now passes. The earlier name appeared in old accumulated
sessions in the same FactorioPad.log. Always use the newest startup entry.

CRITICAL SOURCE FINDING: FactorioCompat/CoreGraphicsShims.m ALREADY defines
and exports kCGDisplayShowDuplicateLowResolutionModes. This is an incorrect
Mach-O two-level native CoreGraphics dylib ordinal, not a missing shim.

Committed follow-up changes include:
- Tools/rebind_guest_symbols.py now remaps this exact CG constant from
  CoreGraphics to FactorioCompat alongside NSAppleEventManager.
- Tests/test_rebind_guest_symbols.py covers the CoreGraphics import ordinal.
- Tools/build_private_duo.py and Tools/audit_macho_imports.py validate both
  imports are routed to FactorioCompat and exported by the packaged shim.

NEXT: pull newest experiment branch, run all targeted binding tests, then run
the FULL expanded native-provider audit on the EXISTING afccbc9 IPA to
understand exactly why its previous audit exited 1. Do not recompile until
all discoverable native provider gaps have been analyzed and fixed, or a
source change truly necessitates a fresh IPA.

When ready, build one corrected IPA with a newly patched original game
guest and version-stamped native app. Then run the complete expanded audit
before another device installation. Continue autonomously per AGENTS.md.


The user's fresh FactorioPad(10).log confirms the newest **actual** device
failure (2026-11-27 01:37 UTC) occurs inside FactorioGuest dlopen:
  Symbol not found: _OBJC_CLASS_$_NSAppleEventManager
  Expected in: /System/Library/Frameworks/Foundation.framework/Foundation
The prior UTType errors appear earlier in the accumulated log, but the newest
error is a different dyld binding: FactorioGuest erroneously looks for the
macOS-only NSAppleEventManager class in native iOS Foundation, even though
FactorioCompat/AppKitShims.m already implements it.

I have committed the fix infrastructure directly to the experiment branch:
- Tools/rebind_guest_symbols.py: symbol-specific Foundation -> FactorioCompat
  dylib ordinal rewrite, supporting chained Mach-O imports and classic binds.
- Tools/patch_factorio.py invokes the rewrite when preparing FactorioGuest.
- Tests/test_rebind_guest_symbols.py: synthetic chained/classic import tests.
- Tools/build_private_duo.py: packaged guest must bind NSAppleEventManager
  to FactorioCompat and the class must be exported by the packaged framework.
- Tools/audit_macho_imports.py: audit both FactorioCompat and NATIVE strong
  imports against iOS SDK rather than passing solely on 169 shim-bound imports.
- The Windows template and loader stamp/report source SHA and build timestamp.

NEXT ACTION: Pull latest experiment source and run
  python -m unittest discover -s Tests -p test_rebind_guest_symbols.py
Fix any test failure independently. Then build a FRESH template and private IPA,
because the Windows native loader/build identity has changed, and validate with
the updated full provider audit. Run:
  python -u F:/FactoriOS/Tools/build_private_duo.py --dmg F:/FactoriOS/factorio_mac_2.1.24.dmg
Do NOT reuse the old guest or old SDK template: the Mach-O guest ordinal
must be repatched from the original 2.1.24 DMG. Do not alter FactorioData,
saves, main, or stable release. If a new native missing symbol is discovered,
resolve it at the correct provider ordinal, rerun focused tests, then rebuild.

1. Use the confirmed device dlopen failure and committed ordinal-rebinding
   fix described above. Do not ask for the existing FactorioPad(10).log again.
   After host checks pass, the next physical install can test for new errors.
2. Check repository/source parity BEFORE changing compatibility shims. As
   independently verified in the linked GitHub repository,
   FactorioPad/FactorioLoader.mm has identical contents in:
   IndecentDad/FactoriOS main,
   experiment/windows-native-ios27, and
   MyNameIsArko/FactorioPad main.
   Therefore claiming the loader source is outdated would be incorrect.
   Compare upstream/newer code in **other modules**, including AppKit shims,
   startup initialization, Swift vs Windows-native Objective-C app shell, and
   Windows build inclusion/linkage.
3. Inspect the exact private IPA contents and hashes; correlate the installed
   app's version/build identity with the intended IPA if possible. The
   Windows template builder currently sets app CFBundleVersion to "1" for
   every build, so a repeated install can be ambiguous. Don't assume a stale
   install without positive evidence.
4. The current Windows-native Objective-C/UIKit app replaces the Swift app
   layer. Compare launch semantics, app lifecycle, loader invocation, native
   frameworks, entitlements, and guest dependencies; do not assume parity.
5. Do NOT treat Tools/audit_macho_imports.py as a comprehensive launch check:
   it verifies FactorioGuest's FactorioCompat-bound imports, not all dyld
   dependencies, reexport paths, rebindings, Objective-C selectors, or the
   actual device runtime.
6. Implement only evidence-supported changes, run focused tests, commit and
   PUSH source changes to the experiment branch. Preserve useful binary
   artifacts and avoid regenerating FactorioData or saves. Rebuild IPA only
   when code or packaging has changed, then report exact SHA-256/commit and
   remaining device-only checks.

## Known historical precedent

Factorio 2.1.24 startup in early November 2026 failed on multiple missing
AppKit globals (NSCalibratedRGBColorSpace,
NSWindowDidChangeOcclusionStateNotification,
NSWindowDidEndLiveResizeNotification, etc.). Upstream 2.1.24 compatibility
work fixed related AppKit symbols and SDL/video startup. DO NOT blindly
recreate those prior fixes: verify current binary exports and actual device
dyld error first.

## Reporting standard

Only call the build "host-static-audit-passed" when the scoped audit passes.
Call it "device-launch-validated" only after the real device executes the
guest successfully. Distinguish confirmed failures from hypotheses.
Never return merely "I haven't diagnosed X" when local evidence is available.
