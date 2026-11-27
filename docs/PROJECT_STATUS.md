# FactoriOS Project Status

## FactoriOS v1.0 baseline — host validated

- User confirms the Factorio 2.1.24 port works fully on iPhone Duo. Retained device-confirmed fallback: `F:\FactoriOS\dist\private-duo-ios27-routing-20261127-010338-b79857c\FactorioPad.ipa` (SHA-256 `b656cefa5ef5e52d5bbc2d7509c1d977ddb7a01d04ba0a57dc34b2e08667a8bf`).
- New universal candidate: `F:\FactoriOS\dist\private-duo-ios27-universal-external-pointer-c3b1018\FactorioPad.ipa`; SHA-256 `b1a05f4a40576dfe714109cc9d77fcd5182b03014fc8c5f8f7292e49096b7b61`.
- Candidate source `c3b101845e2e3732b1e7458303eca187fe502dd6`; embedded app hash `f092e2b4f412c945403c8fc20927c744e61b01b0de0b89526c40c3ddd340f34b`. Guest SHA-256 unchanged: `bc21ab31d38c73470f3a31c9be031eb8759577a04276e7ed4c94a7005527dffc`; compat SHA-256 unchanged: `ff2d265a2e87cadb0b53c1c1b57368dd67fa786c3bcb598a87059091211f1829`.
- The candidate declares `UIDeviceFamily [1,2]`, `UIRequiresFullScreen false`, and iPad portrait/landscape support. It changes only the app executable and Info.plist relative to the prior universal package; ZIP contents and permissions were verified.
- The separate FactorioData folder and saves were not accessed. The signed/installed and physically confirmed Duo fallback remains unchanged.

## Validation and implementation

- Windows SDK 27.2 arm64/iOS game-free template compiled and passed `test_windows_native_ipa.py` package validation.
- Passed tests: platform build boundary (4), Duo UIKit UX (6), upstream routing (4), external pointer routing (6).
- Exact-candidate Mach-O audit passed: 319 FactorioCompat strong/lazy bindings verified, including 160 via SDK-probed reexports; 564 native imports checked; zero unverified.
- UIKit external pointer path now gates relative mouse input on capture, routes unlocked iPad pointer/click/scroll through scene events, and releases button state on lock change. iPhone retains its raw input path.
- Original Swift iPad implementation remains unchanged versus own main and upstream main. The Windows shell is not full touch guide/custom keyboard parity. It does not explicitly create or place gameplay in a separate external-display scene.
- Older superseded template/private IPA binaries were removed, freeing 99,648,827 bytes. The current candidate, device-confirmed Duo fallback, audit reports/logs, FactorioData and saves were kept.
- Original Xcode build is unverified because the available Tahoe VM is Intel and cannot run the required Apple-silicon Xcode 27 toolchain.

## Next step

Treat the universal candidate as the v1.0 host-validated baseline. Sign/install it and test on iPad with and without an external monitor, including pointer capture/release, cursor movement/clicks/scroll, keyboard/controller, and actual scene geometry. Retest it on Duo before replacing the known-good fallback. Do not claim separate-monitor gameplay placement without verifying it on hardware.
