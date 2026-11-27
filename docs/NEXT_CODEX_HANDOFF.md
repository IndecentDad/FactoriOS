# FactoriOS — iPad and external-display validation

## Current known-good state

- User confirms Factorio 2.1.24 is fully supported on the physical iPhone Duo.
- Preserve confirmed Duo IPA `F:\FactoriOS\dist\private-duo-ios27-routing-20261127-010338-b79857c\FactorioPad.ipa`, SHA-256 `b656cefa5ef5e52d5bbc2d7509c1d977ddb7a01d04ba0a57dc34b2e08667a8bf`.
- Branch: `experiment/windows-native-ios27`; latest code commit `c3b1018`.
- No FactorioGuest compatibility or FactorioData changes were made. Existing saves and older IPAs remain untouched.

## Source comparison and feature boundary

The original `FactorioPadApp.swift`, `FactorioMetalView.swift`, `FactorioControlsView.swift`, `FactorioTouchControls.swift`, `FactorioOnScreenKeyboard.swift`, `FactorioControllerCursor.swift`, `FactorioKeyboardBridge.m`, and `FactorioControllerBridge.m` match both own `main` and upstream `MyNameIsArko/FactorioPad` `main`. The `FactorioPadApp.swift` and `FactorioMetalView.swift` files also match `origin/external-display`; there are no unmerged external-display changes in those files to cherry-pick.

The Swift/Xcode app provides the original touch guide/palette, custom on-screen keyboard/text entry, physical keyboard/mouse, native controller and controller cursor, graphics/input preferences, save sync, and pointer handling. On iPad it requests pointer capture when no external screen is connected and the native-controller path is active; display connection/disconnection and lock changes trigger reevaluation. Unlocked pointer position, clicks and scrolls route through UIKit, using the actual scene screen for geometry. The source does not implement an explicit separate external-display gameplay window/scene manager; do not claim gameplay moves to the monitor. Actual scene creation/placement requires hardware validation.

The Windows SDK builder intentionally compiles the Objective-C UIKit shell and excludes it from the original Swift Xcode target. Its shell includes Duo geometry, native controller, mouse/keyboard, cursor, touch, settings and save-sync paths. The UIKit shell does not replicate the complete Swift touch guide/palette/custom keyboard. Keep the original Swift app as the full iPad UX path; do not rewrite it in Objective-C or merge the Windows shell to main.

## Focused changes

- Windows bundle metadata is universal (`UIDeviceFamily [1,2]`, `UIRequiresFullScreen false`) and matches the Xcode target. Regression tests verify the Xcode target still includes its Swift source group and excludes Windows-only entry/UI files.
- The UIKit shell now gates relative `GCMouse` movement/buttons/scrolling on iPhone or actual pointer capture. Unlocked iPad scenes use absolute indirect-pointer touches, button masks, UIKit scroll gestures and hover position. Lock changes release pointer button state; mouse disconnect is handled. This preserves the existing iPhone raw-mouse path.
- Commits: `61811ab` (external pointer routing and tests), `c3b1018` (CGPoint scroll accumulator compile fix). Earlier universal-metadata/Xcode-boundary fixes are in `bc08e5e` and its ancestors.

## Host validation and artifacts

- Required tests passed: `test_platform_build_boundary.py` (4), `test_windows_native_ipa.py` (template validator), `test_duo_uikit_ux.py` (6), `test_upstream_framework_routing.py` (4), and `test_windows_external_pointer.py` (6).
- Fresh game-free template compiled arm64/iOS SDK 27.2 and passed package validation: `F:\FactoriOS\dist\FactoriOS-template-ios27-universal-external-pointer-c3b1018.ipa`.
- The previous private IPA lacked `UIDeviceFamily` and `UIRequiresFullScreen`. New universal candidate: `F:\FactoriOS\dist\private-duo-ios27-universal-external-pointer-c3b1018\FactorioPad.ipa`.
- Candidate IPA SHA-256 `b1a05f4a40576dfe714109cc9d77fcd5182b03014fc8c5f8f7292e49096b7b61`; app `f092e2b4f412c945403c8fc20927c744e61b01b0de0b89526c40c3ddd340f34b`; guest unchanged `bc21ab31d38c73470f3a31c9be031eb8759577a04276e7ed4c94a7005527dffc`; compat unchanged `ff2d265a2e87cadb0b53c1c1b57368dd67fa786c3bcb598a87059091211f1829`.
- The IPA repack changed only `FactorioPad` and `Info.plist`; all other entries and permissions stayed identical. No FactorioData was read, copied or regenerated.
- Full exact-IPA audit: 319 compatibility strong/lazy bindings verified (160 via native reexports), 564 native imports checked, zero unverified. This is host-side validation only.
- The original Xcode/iPad build was not run: the available Tahoe VM is Intel and cannot run the required Apple-silicon Xcode 27 toolchain. Do not try to substitute another SDK.

## Required physical tests

Sign/install the candidate while retaining the known-good Duo IPA. On iPad, with no monitor, test pointer capture and mouse/keyboard/controller/touch input. Connect an external monitor and verify pointer unlock, system cursor movement between displays, clicks, scrolling, keyboard and controller behavior; disconnect and verify capture policy reapplies. Record scene/window/screen geometry. Confirm whether iPadOS creates/supplies a second scene—this project does not explicitly launch or place gameplay in a separate monitor scene. Recheck the iPhone Duo candidate before replacing its working installation.
