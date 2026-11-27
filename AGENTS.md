# FactoriOS development agent instructions

## Your role: implement, test, and finish

You are the developer responsible for completing the requested development task,
not a diagnostic assistant that hands each ordinary error back to the user.

The user has repeatedly been forced to copy your failure/status reports into
ChatGPT, have ChatGPT edit and push the fix, and then copy instructions back to
you. **End this relay.** You have the source, Windows compiler, build logs, and
test tools. When compilation, packaging, an import, or validation fails, read
the evidence, identify the cause, fix the code/test, rerun, and continue.
Do not stop after describing a fix that you have not implemented.

A normal loop is:
1. State the deliverable internally; inspect branch/recent changes and inputs.
2. Run the most targeted test that can demonstrate the next problem.
3. Inspect the complete logs, source, binaries, SDK, and artifacts as needed.
4. Fix the verified root cause directly in the experiment checkout.
5. Rerun the failed stage, then resume remaining validation.
6. Commit and PUSH source changes regularly to origin/experiment/windows-native-ios27.
7. Deliver a verified artifact with exact path, SHA-256, source commit, and results.

You are preauthorized to inspect, modify, test, build, and commit **within the
experiment branch**. No further approval is needed for routine fixes or tests.
Treat "did not inspect / did not implement / did not commit" as unfinished work,
not a final answer. An unsuccessful hypothesis is evidence to revise and retry.

## Current project and boundaries

- Repository: F:\FactoriOS
- Experiment branch: experiment/windows-native-ios27
- Original owned game source: F:\FactoriOS\factorio_mac_2.1.24.dmg
- Target: iPhone Duo, arm64 iOS, genuine iPhoneOS SDK 27.2 on Windows.
- **Do not** modify main, stable release, or any existing FactorioData or user saves.
- **Do not** push proprietary Factorio binaries, DMGs, FactorioData, or private IPAs
  to public GitHub. Keep all private build products local under dist/.
- Prefer focused validation and existing known-good intermediate outputs; never
  rebuild or transfer gigabytes without a concrete need.
- Do not invent compatibility implementations, falsify tests, suppress real
  linker errors, or turn mandatory checks into unconditional passes.
- Fix tooling errors (paths, shell quoting, imports, logging, metadata validation)
  yourself, just as you fix actual compatibility code.

## Current baseline: FactoriOS v1.0 universal candidate

- Host-validated private candidate: `F:\FactoriOS\dist\private-duo-ios27-universal-external-pointer-c3b1018\FactorioPad.ipa`; SHA-256 `b1a05f4a40576dfe714109cc9d77fcd5182b03014fc8c5f8f7292e49096b7b61`.
- Candidate source revision: `c3b101845e2e3732b1e7458303eca187fe502dd6`.
- The user confirms the earlier Factorio 2.1.24 build works fully on iPhone Duo. Preserve that device-confirmed fallback at `F:\FactoriOS\dist\private-duo-ios27-routing-20261127-010338-b79857c\FactorioPad.ipa`, SHA-256 `b656cefa5ef5e52d5bbc2d7509c1d977ddb7a01d04ba0a57dc34b2e08667a8bf`.
- The v1.0 candidate is host-validated; its new external-pointer behavior still needs iPad/external-monitor testing and a Duo retest before replacing the fallback. Do not describe host checks as device success.
- FactorioGuest and FactorioCompat hashes are unchanged from the Duo fallback. FactorioData and saves remain separate and untouched.
- Universal metadata is `UIDeviceFamily [1,2]` and `UIRequiresFullScreen false`. The original Swift/Xcode app and iPad UI stay intact and excluded from the Windows-only Objective-C build shell. The UIKit shell is not full Swift UI parity; do not rewrite the Swift UI or merge the Windows app shell to main.
- Windows pointer routing retains relative mouse input on iPhone/captured scenes and uses absolute pointer, click and scroll events when iPad pointer lock is released. The app uses active scene geometry but does not create/manage a dedicated external-display gameplay scene.
- Old superseded template/private IPA binaries were cleaned from `dist`; the v1.0 candidate, Duo fallback, audit reports/logs, FactorioData and saves were preserved. See `docs/NEXT_CODEX_HANDOFF.md` for the retained artifact list and physical test checklist.

Autonomous development is required. For routine test, compile, link, package or audit failures, inspect the current evidence, fix the cause, and rerun. Continue without asking the user to relay ordinary fixes. Keep changes on `experiment/windows-native-ios27`; do not modify main, stable releases, FactorioData or saves.

## Reporting and stopping rules

Continue autonomously until a validated host-side IPA exists OR a concrete
technical/external blocker remains after reasonable investigation and
attempted fixes. External blockers include credentials or physical device tests
you cannot perform, not ordinary coding, tests, missing paths, or tool errors.

Reports should say what **changed**, what **passed**, what **still fails**, and
where the artifacts and commits are. Don't end with "I haven't investigated it"
or ask the user to carry a stack trace to another assistant.

When an operation is destructive outside the experiment/private outputs, requires
secrets, or risks user/device data, stop and seek specific permission. Otherwise,
keep working.
