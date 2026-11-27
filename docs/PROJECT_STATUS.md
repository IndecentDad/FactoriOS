# FactoriOS Project Status

## Latest — Duo runtime success and UI refinements (not yet built)

- The restored-upstream Factorio 2.1.24 private IPA launched and rendered gameplay on a physical unfolded iPhone Duo. Known-good rollback SHA-256: `f74007552be18f9fa1fe795ba2b40d1e87136bc31d6ba92e24243a4d077549d9`. Preserve that IPA and the existing FactorioData/saves.
- Device screenshots show the game view still inset/shifted in landscape, portrait gameplay consuming both panels, two persistent top overlay controls, missing keyboard shortcut, and an unattractive nonadaptive launcher.
- UI-only experiment edits committed: full-scene unfolded Duo landscape viewport; portrait upper-panel game + lower-panel touch controls; controller-aware touch pad; small always-visible keyboard control in lower-right (tap to type, hold for game menu); dynamically hidden Import action when local FactorioData validates; responsive dark game/settings launcher with graphics, controller, save sync, and diagnostics.
- A read-only FactorioData version/presence method was added to FactorioLoader; game binary patching, FactorioCompat and existing save logic remain unchanged. Build metadata now supports portrait.
- **IMPORTANT: these new UI changes have NOT been Windows-compiled or physically device-tested.** Codex must run game-free regression tests, compile the SDK 27.2 app, fix any source/SDK issues, generate one new private no-data IPA, run full audit, then request a focused Duo device test. See `docs/NEXT_CODEX_HANDOFF.md` for acceptance criteria.


## Latest — restored original upstream framework routing

- The prior Windows SDK 27.2 build pipeline was NOT semantically equivalent
  to the Xcode-built app. It changed Tools/patch_factorio.py to route original
  macOS Foundation/CoreGraphics/CoreVideo/Metal/Security/CoreAudio/AudioToolbox
  imports directly to native iOS frameworks, bypassing FactorioCompat.
- Upstream MyNameIsArko/FactorioPad and this fork's main have the exact same
  canonical Mach-O patcher (Git blob 58bfe0afd0aaebdce60aac83a4c9b65ad12d710e).
  The Windows experiment now restores that exact file.
- Original FactorioCompat.xcconfig already specifies reexports of all relevant
  native providers. Windows now derives LC_REEXPORT_DYLIB requirements from
  that canonical SHIM_FRAMEWORKS set and retains the MobileCoreServices fallback.
- Obsolete one-symbol Mach-O import rebinding has been deleted; a new
  game-free test verifies canonical routing and Xcode configuration parity.
- Tools/build_private_duo.py now rejects native Foundation/CoreGraphics/etc
  guest routing; the expanded Mach-O audit tests the full reexport set.
- **Next:** Codex on Windows must run the new routing regression test, inspect
  existing afccbc9 failed audit evidence, build a *fresh* SDK 27.2 template
  and original-DMG-patched 2.1.24 guest, resolve all real host audit failures,
  then provide a new IPA for physical Duo launch testing.
- **No new IPA has been created or tested by these source commits.**
  Source changes do not establish on-device launch or screen geometry.


## Windows-native experiment

- Worktree: `F:\FactoriOS`, branch `experiment/windows-native-ios27`, based on requested commit `a805cc79dbbe40c717c575e9d5577f36e1dd76e2`. Production `main` and `FactoriOS-latest` were not changed.
- Latest branch commit: `63cafc1b3e289cd3cecc3216721fb337ba05ba93`. Compiled source is from `d02b18c4b40276ea22761a4d8dc3f9957ad99b0f`; later commits only format source or update documentation.
- Windows toolchain: LLVM/Clang and ld64.lld 23.1.4; genuine iPhoneOS SDK 27.2 at `F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk`. Windows Swift compiler is unavailable, so the Xcode Swift app layer is bypassed with a native Objective-C/UIKit entry layer.
- `Tools/build_windows_template.py` compiles the 19 existing FactorioCompat C/Objective-C sources, existing `FactorioLoader.mm`, and new Objective-C app/input/save-sync sources. The ObjC++ file uses `-fno-modules` because Windows Clang's Foundation module importer produced incomplete declarations.
- Latest successful game-free template: `F:\FactoriOS\dist\FactoriOS-windows-sdk27.2-input-cursor.ipa` (2,117,096 bytes). Both app and FactorioCompat are arm64/iOS Mach-O and record SDK 27.2. Framework linkage, app metadata, ZIP executable bits, marker, and absence of guest/data files were validated.
- Added Objective-C UIKit scene/window shell, Duo safe-area/16-point phone corner inset, scene-based landscape request, native Metal drawable sizing/logging, game-data import, graphics/native-controller preferences, AVAudioSession setup, conflict-aware ZIP save sync, basic movement/action touch pad, HID keyboard mapping, GCMouse pointer/buttons/scroll, a custom cursor view, and the current native pointer-lock policy.
- Validation passed: full Windows compile/link/package; `Tests/test_windows_native_ipa.py`; existing `Tests/test_package_ipa.py`.

## Outstanding

- Not run on simulator/device. The Windows host currently detects no iPhone, and PlumeImpactor is not callable there. Physical Duo viewport, Metal drawable, touch alignment, and gameplay with the prepared private 2.1.24 package remain unverified.
- Full Swift touch-controls guide/palette and some custom controller/UI behavior are not yet at parity. External-display scene routing has not been validated in the new UIKit shell.
- The companion `package_ipa.py template` accepted and reprocessed the final IPA to another validated game-free package. `Tests/test_companion.py` could not run because the selected Windows Python environment lacks PyInstaller; no package was installed.
- Prepared a private local device package at `F:\FactoriOS\dist\private-duo-test-2.1.24\` from the existing desktop DMG. Both embedded guest and separate `FactorioData` report version 2.1.24. This ignored folder was not committed or pushed.
- Next validation, when directed: connect the iPhone Duo to Windows, sign/install the private package with PlumeImpactor, capture scene/window/safe/game/drawable geometry logs, then test gameplay/input, fold transitions, and an external display. Keep `main` and the stable release untouched.
