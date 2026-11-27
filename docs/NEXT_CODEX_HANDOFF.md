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
