# Windows-native FactoriOS template build (experimental)

This pipeline is for branch `experiment/windows-native-ios27`. It uses Windows LLVM/Clang and ld64.lld with the extracted iOS 27.2 SDK; no Xcode or macOS build host is used.

From `F:\FactoriOS` in PowerShell:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" `
  Tools\build_windows_template.py `
  --output F:\FactoriOS\dist\FactoriOS-template-windows-sdk27.2.ipa

& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" `
  Tests\test_windows_native_ipa.py `
  F:\FactoriOS\dist\FactoriOS-template-windows-sdk27.2.ipa
```

The build expects LLVM under `C:\Program Files\LLVM\bin`, SDK at `F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk`, and Pillow in the selected Python environment for icon resizing. Override SDK/build/LLVM locations with `FACTORIOS_IOS_SDK`, `FACTORIOS_BUILD_DIR`, and `LLVM_BIN`.

The result is unsigned and game-free. Package it with the existing Windows companion and sign it for installation. The build validates arm64/iOS `LC_BUILD_VERSION` metadata, the app-to-compatibility-framework dependency, bundle metadata, executable ZIP permissions, and absence of FactorioGuest/FactorioData. These checks do not prove launch, gameplay, external-display routing, or Duo geometry.

Current Objective-C app shell ports launch/import, graphics/controller mode preferences, audio session setup, save-folder synchronization, basic touch controls, physical keyboard input, and raw GCMouse input. The Swift UI remains in the source tree as a reference. Full control-guide/overlay parity, pointer-lock behavior, and external-display lifecycle still need review and device validation.
