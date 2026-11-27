# FactoriOS Windows SDK 27.2 — Duo launch baseline and UI cleanup

## Current baseline

- Repository: `F:\FactoriOS`, branch `experiment/windows-native-ios27`.
- Verify the latest Git revision and worktree before beginning.
- The Factorio 2.1.24 private build documented in the previous handoff has launched successfully on the physical iPhone Duo. Treat the working IPA and its embedded guest and compatibility framework as the known-good runtime baseline.
- Preserve the working IPA, FactorioData, saves, main, and stable releases. Do not replace the baseline until a new candidate is validated on-device.
- Host audit passed with exit code 0 and matching IPA SHA-256 `f74007552be18f9fa1fe795ba2b40d1e87136bc31d6ba92e24243a4d077549d9`. Device launch is the runtime confirmation.

## Next task — UI cleanup

Continue focused UI cleanup on `experiment/windows-native-ios27`. Begin by checking Git state, this handoff, and `docs/PROJECT_STATUS.md`. Preserve the confirmed launch baseline, Duo display geometry, Metal rendering, keyboard/controller support, touch controls, saves, and startup logging. Make small reversible changes, validate through the normal Windows SDK 27.2 workflow, and retain the current baseline IPA until a replacement is confirmed on the Duo.

## Autonomous development expectations

Act as the project developer. When a build, test, audit, packaging step, or command fails, inspect the complete current-run evidence, identify the cause, correct the code or tooling, and rerun before continuing. Do not stop at an intermediate error or return an investigation-only report. Continue through routine failures without asking the user to relay fixes. Stop for a genuine external dependency such as physical-device access or credentials, and state the exact boundary.

Commit and push source changes only to `experiment/windows-native-ios27`. Never publish proprietary game executables, DMGs, FactorioData, saves, or private IPAs. Do not modify `main` or stable releases. Keep reports untracked unless requested. Reuse verified intermediate artifacts and avoid rebuilding game data.

## Build and validation references

- Windows SSH alias: `nxwindows`
- Repository: `F:\FactoriOS`
- Original Factorio source: `F:\FactoriOS\factorio_mac_2.1.24.dmg`
- Windows SDK 27.2: `F:\NXNative\1_Development\SDKs\Xcode_27.2\iPhoneOS.sdk`
- Build status/logs: `F:\FactoriOS\dist\build_private_duo_status.json` and `F:\FactoriOS\dist\build_private_duo_logs\`
- Use the current committed `build_private_duo.py` workflow. Confirm status and audit results for the exact IPA. Never infer success from stale appended logs or an earlier run.
- Repatch FactorioGuest from the original DMG whenever guest patching changes. Never patch an already modified guest.
- Physical-device launch and gameplay remain required to validate each new candidate.


## Current UI source changes — compile and validate autonomously

The physical Duo screenshots establish the working guest, but show a letterboxed/
off-center landscape viewport, an overextended portrait game viewport, a crude
button-stack launcher, two persistent top buttons and no always-accessible
keyboard icon. The user wants the Factorio game to use both unfolded panels
edge-to-edge in landscape, the top panel only in portrait, and optional touch
controls on the lower portrait panel. A connected controller may hide touch
controls but must NEVER hide the keyboard shortcut. The NX18 screenshot is a
visual reference for a dark game + settings layout, NOT a request to import
Nintendo assets.

Source now committed on this branch:
- FactorioPad/FactorioUIKitApp.m: responsive dark game hero/settings cards,
  graphics/controller segmented controls, save-sync/log actions, data-ready
  check, hidden Import action when valid FactorioData exists, Play disabled
  when data is missing, and no unsolicited import when the private IPA lacks
  bundled game data.
- FactorioPad/FactorioLoader.h + .mm: read-only validated hasValidGameData
  and installedGameVersion, reusing the existing FactorioDataProblem checker.
- FactorioPad/FactorioTouchUIKit.m: small bottom-right keyboard icon that
  remains reachable with a controller; tap opens a UIKit typing dialog and
  hold opens a Home / Show-or-Hide Touch Controls menu. Removes permanent
  Home and Show Pad top buttons.
- FactorioPad/FactorioUIKitApp.m game controller: no hard-coded extra 16pt
  inset, Duo unfolded landscape Metal game view uses full scene bounds while
  the floating touch UI uses UIKit safe area. Unfolded portrait uses upper
  half for gameplay and lower half for touch controls. Connected controllers
  hide the pad; game view resizes with the UIWindowScene.
- Tools/build_windows_template.py and Tests/test_windows_native_ipa.py:
  portrait is included in the app's supported orientation metadata; no
  hard-coded scene landscape request.
- Tests/test_duo_uikit_ux.py: game-free source invariants for scene/portrait,
  data import readiness, controls and keyboard access.

NEXT REQUIRED ACTIONS (do not stop after a command):

1. Pull origin/experiment/windows-native-ios27 and read updated source.
2. Run python -m unittest discover -s F:/FactoriOS/Tests -p test_duo_uikit_ux.py
   and the existing package/guest routing regression tests.
3. Compile a game-free SDK 27.2 Windows template FIRST. Diagnose and fix
   Objective-C/UIKit linker, ARC, layout and packaging errors yourself;
   commit/push fixes, repeat. Review exact UIView and frame layout to ensure
   keyboard is a touch-hit target even when pad is hidden.
4. Once the game-free app+compat build passes, build ONE new private IPA from
   the original 2.1.24 DMG with --no-data; do not re-import or overwrite
   FactorioData or saves, and preserve the rollback IPA specified above.
5. Run complete import/reexport SDK audit against that exact IPA, check exact
   source commit and hash, then deliver only the new IPA path and checks.
6. The user will do a physical iPhone Duo test. Confirm:
   - landscape is full/centered in both unfolded panels with no unexplained
     right black strip; use the new 'Duo geometry' line (scene/window/screen,
     safe, game, touch, drawable, orientation) if not.
   - portrait game fills TOP half only; touch controls stay on lower half
     (hide with connected controller) and input hitboxes match display.
   - keyboard icon is visible at bottom-right in both modes. Tap to type
     into a genuine in-game text field; hold to open the overlay menu.
   - no permanent Home or Show Pad buttons overlay gameplay.
   - launcher uses responsive two-column landscape cards and scrollable
     portrait cards, does not show Import when data is valid, honors graphics
     and controller settings and preserves sync.
7. Stop for hardware-only evidence after successfully building/validating
   the new private IPA. No more random compatibility symbol changes.
