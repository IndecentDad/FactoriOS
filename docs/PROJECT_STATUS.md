# FactoriOS Project Status

## Windows-native experiment

- Worktree: `F:\FactoriOS`, branch `experiment/windows-native-ios27`, based on requested commit `a805cc79dbbe40c717c575e9d5577f36e1dd76e2`. Production `main` and `FactoriOS-latest` were not changed.
- Windows toolchain: LLVM/Clang and ld64.lld 23.1.4; genuine iPhoneOS SDK 27.2 at `F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk`. Windows Swift compiler is unavailable, so the Xcode Swift app layer is bypassed with a native Objective-C/UIKit entry layer.
- `Tools/build_windows_template.py` compiles the 19 existing FactorioCompat C/Objective-C sources, existing `FactorioLoader.mm`, and new Objective-C app/input/save-sync sources. The ObjC++ file uses `-fno-modules` because Windows Clang’s Foundation module importer produced incomplete declarations.
- Latest successful game-free template: `F:\FactoriOS\dist\FactoriOS-windows-sdk27.2-final.ipa` (2,117,096 bytes). Both app and FactorioCompat are arm64/iOS Mach-O and record SDK 27.2. Framework linkage, app metadata, ZIP executable bits, marker, and no guest/data files were validated.
- Added Objective-C UIKit scene/window shell, Duo safe-area/16-point phone corner inset, scene-based landscape request, native Metal drawable sizing/logging, game-data import, graphics/native-controller preferences, AVAudioSession setup, conflict-aware ZIP save sync, basic movement/action touch pad, HID keyboard mapping, GCMouse pointer/buttons/scroll, a custom cursor view, and the current native pointer-lock policy.
- Validation passed: full Windows compile/link/package; `Tests/test_windows_native_ipa.py`; existing `Tests/test_package_ipa.py`.

## Outstanding

- Not run on simulator/device. The Windows host currently detects no iPhone, and PlumeImpactor is not callable there. Physical Duo viewport, Metal drawable, touch alignment, and gameplay with the prepared private 2.1.24 package remain unverified.
- Full Swift touch-controls guide/palette and some custom controller/UI behavior are not yet at parity. External-display scene routing has not been validated in the new UIKit shell.
- The companion `package_ipa.py template` accepted and reprocessed the final IPA to another validated game-free package. `Tests/test_companion.py` could not run because the selected Windows Python environment lacks PyInstaller; no package was installed.
- Prepared a private local device package at `F:\FactoriOS\dist\private-duo-test-2.1.24\` from the existing desktop DMG. Both embedded guest and separate `FactorioData` report version 2.1.24. This folder is ignored and was not committed or pushed.
- Keep stable release and `main` untouched. Next: finish the missing UI/input parity, run a signed private IPA through the existing companion, connect the iPhone Duo to Windows, sign/install the private package with PlumeImpactor, capture the scene/window/safe/game/drawable geometry logs, then test gameplay/input and an external display before considering any stable release update.
