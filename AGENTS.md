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

## Active work: Duo launch baseline and UI cleanup

The Factorio 2.1.24 private build documented in `docs/NEXT_CODEX_HANDOFF.md` has launched successfully on the physical iPhone Duo. Treat it as the known-good runtime baseline. Continue with focused UI cleanup on `experiment/windows-native-ios27` while preserving the working IPA and all user data.

Autonomous development is required. When a routine command, compile, test, packaging step, or audit fails, inspect its current-run log and relevant source, fix the root cause, and rerun. Do not stop after diagnosing an ordinary error or ask the user to relay fixes between sessions. Stop only at a genuine external dependency such as physical hardware access or credentials. Keep commits on the experiment branch and do not modify `main`, stable releases, FactorioData, or saves.

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
