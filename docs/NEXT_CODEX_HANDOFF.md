# Next Codex Session — FactoriOS Windows-Native Build

## Session instruction

Read this handoff and the linked project status, verify the checkout state, then **wait for the user's next instruction**. Do not resume implementation, build, test, sign/install, publish, or push anything automatically.

## Repository and branch

- Repository: `IndecentDad/FactoriOS`
- Windows worktree: `F:\FactoriOS`
- Experimental branch: `experiment/windows-native-ios27`
- Last recorded commit: `63cafc1b3e289cd3cecc3216721fb337ba05ba93`
- Starting baseline: `a805cc79dbbe40c717c575e9d5577f36e1dd76e2`
- `main` and the stable `FactoriOS-latest` release were not modified.
- `F:\NXNativeWindows` is a separate, user-modified toolchain checkout. Preserve it; this experiment reused its installed Windows tooling without editing that checkout.

## Read before doing anything else

1. Applicable `AGENTS.md` instructions and current Git state.
2. [`PROJECT_STATUS.md`](PROJECT_STATUS.md) for verified progress, artifacts, tests, and blockers.
3. [`WINDOWS_NATIVE_BUILD.md`](WINDOWS_NATIVE_BUILD.md) for the reproducible Windows build and validator commands.

Then compare the current branch and HEAD to the values above. Git history and source are authoritative if this file is stale. Preserve all local changes and ignored user data.

## Current state at handoff

- Windows LLVM/Clang and ld64.lld 23.1.4 compile the Objective-C/C application and FactorioCompat against the genuine iOS 27.2 SDK.
- The latest game-free candidate is `F:\FactoriOS\dist\FactoriOS-windows-sdk27.2-input-cursor.ipa` (2,117,096 bytes). The private local Factorio 2.1.24 test package is under `F:\FactoriOS\dist\private-duo-test-2.1.24\`; neither artifact is tracked or published.
- Static build and package checks passed. No simulator or physical-device runtime test has been performed.
- The Windows host had no iPhone connected, and PlumeImpactor was not callable. Duo geometry/gameplay and external-display behavior remain unverified. Some Swift touch UI/controller parity remains outstanding.

## Await instruction

After confirming the state, report a short status and stop. Do not make speculative fixes or run expensive commands. Continue only when the user gives a specific next task. If the user asks for physical-device validation, first confirm the Duo is connected/unlocked and use the existing signing/install workflow; keep the private game package local and never publish it. Any future source changes belong on `experiment/windows-native-ios27`, not `main`, unless the user explicitly redirects the target.
