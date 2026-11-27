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

The user reports this IPA produced the **same device-side failure as the
previous candidate**, despite the static audit passing. The exact NEW log
message has not yet been supplied in the active chat. Do NOT assume it is the
same missing symbol unless the device log supports that.

1. Obtain the NEW FactorioPad.log / FactoriOS.log or device crash/dyld
   diagnostic that identifies the actual failing library, symbol, dependency,
   entitlement, launch phase, and binary version. Read the whole relevant
   startup sequence, not only the last line. If device logs are inaccessible
   from the Windows host, give one precise request for the required log and
   perform other non-destructive checks locally while awaiting it.
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
