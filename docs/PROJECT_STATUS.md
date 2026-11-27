# FactoriOS Project Status

## Current milestone — Duo UI candidate ready for device validation

- The original Factorio 2.1.24 guest launches on the physical unfolded iPhone Duo. Preserve rollback IPA SHA-256 `f74007552be18f9fa1fe795ba2b40d1e87136bc31d6ba92e24243a4d077549d9`.
- UI work from source `b79857c3` compiled with the Windows iPhoneOS SDK 27.2 and produced a new unsigned private IPA: `F:\FactoriOS\dist\private-duo-ios27-routing-20261127-010338-b79857c\FactorioPad.ipa`.
- Candidate IPA SHA-256: `b656cefa5ef5e52d5bbc2d7509c1d977ddb7a01d04ba0a57dc34b2e08667a8bf`. FactorioGuest SHA-256: `bc21ab31d38c73470f3a31c9be031eb8759577a04276e7ed4c94a7005527dffc`. FactorioCompat SHA-256: `ff2d265a2e87cadb0b53c1c1b57368dd67fa786c3bcb598a87059091211f1829`.
- Build reused `F:\FactoriOS\dist\FactoriOS-template.ipa`, repatched the guest from the original 2.1.24 DMG, and did not access or regenerate FactorioData. Existing saves and baseline were left untouched.
- Tests passed: Duo UIKit UX regression (6); upstream framework-routing regression (4); game-free template package validation (arm64/iOS SDK 27.2); private IPA structural checks; full exact-IPA audit (319 compatibility bindings verified, 564 native bindings checked, zero unverified strong/lazy imports).
- Build log: `F:\FactoriOS\dist\build_private_duo_logs\ios27-routing-20261127-010338-b79857c.log`. Source changes were not required; compiled source revision remains `b79857c3`.

## Next step

Sign/install the new IPA on the physical Duo and validate unfolded landscape geometry, portrait upper/lower panel allocation, controller-aware touch controls, persistent keyboard access, and launcher behavior. See `docs/NEXT_CODEX_HANDOFF.md` for the detailed checklist. Do not replace the rollback IPA until device validation succeeds.

## Boundaries and execution

Work only on `experiment/windows-native-ios27`; preserve main, stable releases, FactorioData, saves, and the known-good rollback IPA. Keep reports untracked and private game artifacts out of GitHub. Continue through routine command, test, compile, linker, packaging, and audit failures by inspecting evidence, correcting the cause, and rerunning. Stop only for a genuine external dependency such as physical-device testing.
