## Platform-parity correction — original iPad UI must be preserved

The original Xcode project in main and experiment has the EXACT SAME Git blob
(897533bcdfe0a93432b11408b1f781db89e00472), with
TARGETED_DEVICE_FAMILY = "1,2" and UIRequiresFullScreen = NO.
The experiment comparison with main shows zero Swift files modified or deleted.
The iPad/Swift functionality was not removed from GitHub.

However, Tools/build_windows_template.py compiles only .c/.m/.mm sources.
It does not compile ANY of the Swift UI; it uses FactorioUIKitApp.m as its
replacement app shell. THIS IS NOT feature parity with the established
FactorioPad iPad implementation: the old touch guide/palette, external display
workflow, and other Swift-specific features may be absent in this IPA.
Do not call the Windows build a replacement for the production iPad app.

The Windows Info.plist generator previously OMITTED UIDeviceFamily; we have
fixed it to [1,2] matching the original Xcode target and added a packaging
regression assertion (UIRequiresFullScreen remains NO). This fixes the
universal-install targeting metadata. IT DOES NOT restore old Swift-only UX.
A small / windowed iPad presentation may additionally be normal iPadOS
windowing; check window size and stage/windowing mode without assuming
the app has lost iPad support.

Preservation plan:
1. Keep main/Xcode Swift iPad build pipeline and any known-good iPad IPA intact.
2. Keep Windows SDK27 Duo native Objective-C app shell on experiment only.
3. Do not rewrite or reimplement the Swift iPad interface in Objective-C
   just to address an incorrect Windows-produced IPA's device-family metadata.
4. For iPad support, use the original Xcode build path for now; separately
   verify native iPad packaging and UX of the Windows shell if a SINGLE
   universal Windows-built IPA is an explicit goal. That latter feature parity
   cannot be claimed without implementation and hardware tests.
5. First run game-free Windows template build and
   Tests/test_windows_native_ipa.py to verify UIDeviceFamily [1,2].
   This is a packaging-only change. No FactorioGuest or FactorioData rebuild
   or save-file changes are needed.
6. Do not replace the user's stable iPad installation with this experiment
   pending comparison. Do not merge the experiment's Objective-C shell into
   main without an explicit iPad parity review.


# FactoriOS Windows SDK 27.2 — Duo UI validation

## Known working baseline

- Repository: `F:\FactoriOS`, branch `experiment/windows-native-ios27`.
- The original Factorio 2.1.24 guest launches and renders on the physical unfolded iPhone Duo.
- Preserve rollback IPA `F:\FactoriOS\dist\private-duo-ios27-routing-20261126-204853-2b75de1\FactorioPad.ipa`, SHA-256 `f74007552be18f9fa1fe795ba2b40d1e87136bc31d6ba92e24243a4d077549d9`.
- Never modify main/stable, FactorioData, or saves. Never publish private game artifacts.

## Latest UI candidate

- Source used for the build: `b79857c3` on `experiment/windows-native-ios27`.
- Game-free Windows SDK 27.2 template: `F:\FactoriOS\dist\FactoriOS-template.ipa`.
- Private candidate: `F:\FactoriOS\dist\private-duo-ios27-routing-20261127-010338-b79857c\FactorioPad.ipa`.
- IPA SHA-256: `b656cefa5ef5e52d5bbc2d7509c1d977ddb7a01d04ba0a57dc34b2e08667a8bf`.
- Guest SHA-256: `bc21ab31d38c73470f3a31c9be031eb8759577a04276e7ed4c94a7005527dffc`.
- Compat SHA-256: `ff2d265a2e87cadb0b53c1c1b57368dd67fa786c3bcb598a87059091211f1829`.
- Build reused the template, repatched the guest from the original DMG, and explicitly did not access or regenerate FactorioData. Candidate is unsigned and awaits physical Duo UX validation.

## Host validation completed

- `test_duo_uikit_ux.py`: 6 tests passed.
- `test_upstream_framework_routing.py`: 4 tests passed.
- Game-free template compiled and passed arm64/iOS SDK 27.2 package validation.
- Private package and embedded-binary checks passed. Exact-candidate Mach-O audit passed: 319 FactorioCompat strong/lazy bindings verified (160 via verified reexports); 564 native strong/lazy imports checked; 0 unverified in either group.
- Build log/status: `F:\FactoriOS\dist\build_private_duo_logs\ios27-routing-20261127-010338-b79857c.log` and `F:\FactoriOS\dist\build_private_duo_status.json`.
- No source correction was needed for this build. Rebuild only after a verified source change.

## Next task — physical UI validation

Sign/install the new candidate in SideStore/PlumeImpactor and test on the Duo. Confirm:

1. Landscape game view is centered and edge-to-edge across both unfolded panels; no unexpected black strip.
2. Portrait gameplay uses the upper panel, with touch controls allocated to the lower panel.
3. A connected controller hides touch controls without hiding the keyboard icon.
4. Keyboard icon is visible in both orientations; tap opens typing UI, long press opens its menu.
5. No persistent Home/Show Pad overlays remain. Launcher cards/settings and conditional data-import behavior remain correct.
6. Record the build identifier and `Duo geometry` log if geometry or hit targets are wrong. Compare against the preserved rollback IPA.

## Autonomous development

Continue as the project developer through ordinary test, compile, link, packaging, and audit failures. Read the current-run evidence, fix the verified cause, and rerun; do not stop at an intermediate error or ask the user to relay routine fixes. Commit/push source changes only to `experiment/windows-native-ios27`. Stop at physical-device evidence or another genuine external dependency, and report exact results.
