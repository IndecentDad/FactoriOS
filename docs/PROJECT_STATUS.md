# FactoriOS Project Status

## Current state

- Working branch: `external-display` at `9733b9f` before this status update.
- Upstream PR #34 (`1e54b7b`) is an ancestor and all six compatibility files are present.
- The branch retains the local AppKit symbol/behavior fixes, cursor visibility query, external-display behavior, input bridges, FactoriOS template, branding, and Windows companion packaging.
- The checkout is six commits ahead of `origin/external-display` after this status note; none have been pushed.

## Validation

- `Tests/test_package_ipa.py` and `Tests/test_factorios_package_ipa.py`: passed.
- Shell syntax and `git diff --check`: passed.
- `Tests/test_prepare_guest.py` cannot run here because `/usr/libexec/PlistBuddy` is unavailable.
- `Tests/test_ios_compatibility.sh` and the Xcode unit tests require macOS tools; this Synology host has no `xcodebuild` or `xcrun`.
- No full iOS build or device launch test has been performed.

## Next step

After approval, push `external-display` and run the template workflow with `source_ref=external-display`. The workflow defaults to `main`; its selected source must include the five local commits. Then install the generated template IPA and test FactorioGuest on the iPad. Do not claim runtime success until device-tested.
