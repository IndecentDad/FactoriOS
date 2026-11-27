# FactoriOS Project Status

## Duo baseline

- User-confirmed: Factorio 2.1.24 now fully launches and works on iPhone Duo. Preserve the confirmed IPA `F:\FactoriOS\dist\private-duo-ios27-routing-20261127-010338-b79857c\FactorioPad.ipa` (SHA-256 `b656cefa5ef5e52d5bbc2d7509c1d977ddb7a01d04ba0a57dc34b2e08667a8bf`).
- Keep existing FactorioData and saves untouched. The existing private build contains no FactorioData and uses separate installed data.

## iPad and external-display preservation

- The original Swift/Xcode iPad implementation remains present and unchanged versus own `main` and upstream `MyNameIsArko/FactorioPad` `main` for the requested six Swift UI files and two keyboard/controller bridges. The Xcode target excludes the separate Windows Objective-C entry/UI files.
- Windows template metadata now matches the Xcode target: `UIDeviceFamily = [1,2]`, `UIRequiresFullScreen = false`, portrait/landscape iPad orientations. This removes iPhone-only/compatibility-mode packaging; it does not claim the UIKit shell has all Swift UI parity.
- Upstream Swift input supports touch guide/palette, custom on-screen keyboard, physical keyboard/mouse, controller/cursor, preferences and save sync. On iPad with native controller it captures a physical pointer without an external screen, releases lock when another screen connects, and reapplies the policy on screen/pointer-lock changes. It uses the active scene's screen for geometry and routes unlocked pointer position, clicks and scrolling through UIKit. It does not create/manage a dedicated external-display gameplay scene; separate-screen placement is unverified.
- Windows UIKit already had scene-sized geometry, iPad pointer-lock preference updates and native controller/mouse/keyboard paths. It lacked the Swift raw-versus-unlocked input distinction. Commits `61811ab` and `c3b1018` add capture-gated raw mouse input, indirect-pointer button/position handling, unlocked UIKit scroll events, pointer-lock cleanup and mouse-disconnect cleanup. iPhone Duo remains on its existing raw path.
- The Windows shell's compact touch pad/keyboard dialog is not the full Swift touch-control guide/palette/custom keyboard. Use the original Xcode path for complete existing iPad UI parity; do not port/rewrite it in Objective-C.

## Validated universal candidate

- Source: `c3b1018` on `experiment/windows-native-ios27`.
- Game-free template: `F:\FactoriOS\dist\FactoriOS-template-ios27-universal-external-pointer-c3b1018.ipa` (arm64/iOS SDK 27.2; package validation passed).
- Private IPA: `F:\FactoriOS\dist\private-duo-ios27-universal-external-pointer-c3b1018\FactorioPad.ipa`.
- IPA SHA-256: `b1a05f4a40576dfe714109cc9d77fcd5182b03014fc8c5f8f7292e49096b7b61`.
- FactorioPad SHA-256: `f092e2b4f412c945403c8fc20927c744e61b01b0de0b89526c40c3ddd340f34b`.
- FactorioGuest SHA-256 unchanged: `bc21ab31d38c73470f3a31c9be031eb8759577a04276e7ed4c94a7005527dffc`. FactorioCompat unchanged: `ff2d265a2e87cadb0b53c1c1b57368dd67fa786c3bcb598a87059091211f1829`.
- Repack changed only app executable and Info.plist in the prior universal-metadata IPA. ZIP entries and permissions were preserved. Separate FactorioData was not accessed or copied.
- Tests: platform boundary 4, Duo UX 6, upstream routing 4, external pointer routing 6 passed. `test_windows_native_ipa.py` passed on the game-free template. Full audit of the exact private IPA passed: 319 FactorioCompat strong/lazy bindings verified (160 through SDK-probed reexports), 564 native bindings checked, zero unverified imports.
- Original Xcode build remains unverified here: required Apple-silicon Xcode 27 is unavailable on the Intel Tahoe VM.

## Next step

Sign/install the new private IPA and physically test pointer capture, connect/release, cursor position/movement/clicks/scroll, physical keyboard, and controller behavior on iPad with and without an external monitor. Confirm actual screen geometry and whether iPadOS supplies a separate scene. Recheck Duo on this candidate before replacing its known-good installation; device behavior is not established by the host tests. Preserve all older IPAs.
