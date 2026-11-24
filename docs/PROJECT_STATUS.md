# FactoriOS Project Status

## Current state

- Verified baseline source: `ac8810c4892acf7d511cf0698489274376fe1cda` on `main`.
- Tahoe runs macOS 26.7.1 on `x86_64`. Its installed Xcode 26.6 remains selected and intact.
- The supplied Xcode 27.2 archive was verified and expanded. Its `xcodebuild` is arm64-only, so it cannot run on this VM. Apple’s Xcode 27 release notes confirm Apple silicon is required.
- The extracted iPhoneOS SDK reports 27.2, but Xcode 26.6 does not accept it as a generic iOS build destination. A temporary SDK registration was removed after the check.
- An unchanged game-free template built successfully from the baseline with Xcode 26.6 / iOS SDK 26.5. Its app and FactorioCompat Mach-O metadata both record SDK 26.5; it is not a Duo candidate.

## Duo findings

- The reference Duo implementation uses the active `UIWindowScene` for orientation, leaves the window at 951 × 669 points, and insets the game viewport by safe-area/corner margins to 919 × 637 points. It documents a 2853 × 2007 window drawable and 2757 × 1911 game drawable.
- FactoriOS already creates a window for each scene and logs window/screen geometry. Its CoreGraphics display metrics use a foreground scene’s screen bounds, while the Metal host drawable follows the view bounds and display scale. The game view currently has no equivalent fixed corner inset.
- No FactoriOS display code was changed because the required SDK 27.2 baseline cannot be built on the available x86_64 Tahoe host. No physical Duo geometry was measured in this session.

## Validation and next step

- The baseline template build and packaging validator passed, but used SDK 26.5. Mach-O inspection confirmed arm64 and SDK 26.5 for both app and compatibility framework.
- The reference project notes that its Duo simulator cannot validate normal Factorio graphics because of missing GPU-family/BC texture support; physical-device validation remains necessary.
- Next, use an Apple silicon Mac with Xcode 27.2 or later to build the unchanged baseline with SDK 27.2. Then compare logged scene/window/drawable/input geometry on the Duo and implement safe-area/SDL changes only where measurements show a mismatch. Preserve the current working release until that candidate passes physical-device checks.
