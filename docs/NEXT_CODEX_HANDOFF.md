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
