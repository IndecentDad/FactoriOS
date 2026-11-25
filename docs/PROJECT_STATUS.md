# FactoriOS Project Status

## Windows-native experiment

- Worktree: `F:\FactoriOS`, branch `experiment/windows-native-ios27`, based on requested commit `a805cc79dbbe40c717c575e9d5577f36e1dd76e2`. Production `main` and `FactoriOS-latest` were not changed.
- Windows toolchain: LLVM/Clang and ld64.lld 23.1.4; genuine iPhoneOS SDK 27.2 at `F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk`. Windows Swift compiler is unavailable, so the Xcode Swift app layer is bypassed with a native Objective-C/UIKit entry layer.
- `Tools/build_windows_template.py` compiles the 19 existing FactorioCompat C/Objective-C sources, existing `FactorioLoader.mm`, and new Objective-C app/input/save-sync sources. The ObjC++ file uses `-fno-modules` because Windows Clang’s Foundation module importer produced incomplete declarations.
- Latest successful game-free template: `F:\FactoriOS\dist\FactoriOS-windows-sdk27.2-final.ipa` (2,117,096 bytes). Both app and FactorioCompat are arm64/iOS Mach-O and record SDK 27.2. Framework linkage, app metadata, ZIP executable bits, marker, and no guest/data files were validated.
- Added Objective-C UIKit scene/window shell, Duo safe-area/16-point phone corner inset, scene-based landscape request, native Metal drawable sizing/logging, game-data import, graphics/native-controller preferences, AVAudioSession setup, conflict-aware ZIP save sync, basic movement/action touch pad, HID keyboard mapping, GCMouse pointer/buttons/scroll, a custom cursor view, and the current native pointer-lock policy.
- Validation passed: full Windows compile/link/package; `Tests/test_windows_native_ipa.py`; existing `Tests/test_package_ipa.py`.

## Outstanding

- Not run on simulator/device. Physical Duo viewport, Metal drawable, touch alignment, and launch with a personal packaged FactorioGuest/FactorioData remain unverified.
- Full Swift touch-controls guide/palette and some custom controller/UI behavior are not yet at parity. External-display scene routing has not been validated in the new UIKit shell.
- The companion `package_ipa.py template` accepted and reprocessed the final IPA to another validated game-free package. `Tests/test_companion.py` could not run because the selected Windows Python environment lacks PyInstaller; no package was installed.
- Keep stable release and `main` untouched. Next: finish the missing UI/input parity, run a signed private IPA through the existing companion, then test on iPhone Duo and an external display before considering any stable release update.
