# FactoriOS v1.0 — universal Duo/iPad baseline

## Baseline artifacts

- Project baseline designation: **FactoriOS v1.0, host validated**. This is a project baseline label; the IPA's bundle version remains unchanged.
- Branch: `experiment/windows-native-ios27`.
- Source used for the app binary: `c3b101845e2e3732b1e7458303eca187fe502dd6`.
- New universal private IPA: `F:\FactoriOS\dist\private-duo-ios27-universal-external-pointer-c3b1018\FactorioPad.ipa`.
- IPA SHA-256: `b1a05f4a40576dfe714109cc9d77fcd5182b03014fc8c5f8f7292e49096b7b61`.
- App SHA-256: `f092e2b4f412c945403c8fc20927c744e61b01b0de0b89526c40c3ddd340f34b`.
- Guest SHA-256: `bc21ab31d38c73470f3a31c9be031eb8759577a04276e7ed4c94a7005527dffc`; Compat SHA-256: `ff2d265a2e87cadb0b53c1c1b57368dd67fa786c3bcb598a87059091211f1829`.
- Retained physical Duo fallback: `F:\FactoriOS\dist\private-duo-ios27-routing-20261127-010338-b79857c\FactorioPad.ipa`, SHA-256 `b656cefa5ef5e52d5bbc2d7509c1d977ddb7a01d04ba0a57dc34b2e08667a8bf`.

The new package is universal (`UIDeviceFamily [1,2]`, `UIRequiresFullScreen false`), unsigned, host-validated, and not yet tested on iPad/external display. The prior fallback is the user-confirmed Duo runtime build. New external-pointer code keeps the iPhone raw mouse path but must be rechecked on Duo before replacing that installation.

## Preserved support

The original Swift/Xcode UI files and keyboard/controller bridges remain unchanged against own `main` and upstream FactorioPad `main`. Xcode excludes Windows-only Objective-C entry/UI files. The Swift path remains the full original iPad experience: control guide/palette, custom keyboard, physical input, controllers/cursor, preferences and save sync.

The Swift external-display code updates pointer-lock preference when screens/lock state change, captures on iPad with no external display in the native-controller path, releases capture with an external screen, and uses active scene-screen geometry and UIKit pointer/click/scroll input when unlocked. It does not explicitly create or manage a separate monitor gameplay scene.

The Windows UIKit shell now follows the captured-versus-unlocked input distinction. It is not full touch-guide/custom-keyboard parity; do not rewrite Swift UI or merge the Windows shell to main. Do not alter FactorioGuest compatibility, FactorioData, saves, main or stable releases.

## Completed checks

- Game-free SDK 27.2 arm64/iOS template compilation and universal package validation passed.
- `test_platform_build_boundary.py`: 4 passed.
- `test_windows_native_ipa.py`: passed on the game-free template.
- `test_duo_uikit_ux.py`: 6 passed.
- `test_upstream_framework_routing.py`: 4 passed.
- `test_windows_external_pointer.py`: 6 passed.
- Exact v1.0 candidate audit passed: 319 compatibility bindings verified (160 via SDK-probed reexports), 564 native imports checked, zero unverified.
- IPA repack changed only app executable and Info.plist; guest/compat, all other entries, and executable permissions are preserved. FactorioData/saves were not accessed.
- Superseded builds cleaned: four old game-free templates and three stale private IPA binaries removed (99,648,827 bytes). Current v1.0 candidate, Duo fallback, audit reports/logs and data remain.
- Xcode/iPad compile remains unverified because Intel Tahoe cannot run Apple-silicon Xcode 27.

## Next device validation

1. Sign/install the v1.0 candidate while retaining the Duo fallback.
2. On iPad with no monitor, test pointer capture and physical mouse/keyboard/controller/touch.
3. Connect an external monitor; check pointer release, cursor movement between displays, clicks, scroll, keyboard/controller, and scene/window/screen geometry. Disconnect and check capture reapplies.
4. Verify whether iPadOS provides a separate scene. The app does not explicitly place gameplay on an external screen.
5. Retest on Duo before replacing the fallback. Do not infer device success from host audit results.

## Autonomous development

Continue through ordinary test/build/audit errors by inspecting evidence, fixing the cause, and rerunning. Push source changes only to `experiment/windows-native-ios27`. Do not commit generated reports or proprietary game artifacts.
