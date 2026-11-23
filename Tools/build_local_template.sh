#!/usr/bin/env bash
# Build the game-free iOS wrapper locally with Xcode; optionally publish the
# template and trigger the Windows companion build without GitHub macOS runners.
set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo 'Usage: bash Tools/build_local_template.sh [--publish]' >&2
  exit 2
fi
PUBLISH=0
if [[ $# -eq 1 ]]; then
  if [[ "$1" != "--publish" ]]; then
    echo 'Usage: bash Tools/build_local_template.sh [--publish]' >&2
    exit 2
  fi
  PUBLISH=1
fi
[[ "$(uname -s)" == Darwin ]] || { echo 'Requires macOS and full Xcode.' >&2; exit 1; }
for cmd in xcodebuild xcode-select git python3 sips; do
  command -v "$cmd" >/dev/null || { echo "Missing command: $cmd" >&2; exit 1; }
done
if [[ ! -d "$(xcode-select -p)/Platforms/iPhoneOS.platform" ]]; then
  echo 'Select full Xcode: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer' >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO='IndecentDad/FactoriOS'
TAG='FactoriOS-latest'
SHA="$(git -C "$ROOT" rev-parse HEAD)"
if (( PUBLISH )); then
  command -v gh >/dev/null || { echo 'Install GitHub CLI (gh) to publish.' >&2; exit 1; }
  gh auth status >/dev/null || { echo 'Run gh auth login first.' >&2; exit 1; }
  REMOTE_SHA="$(git -C "$ROOT" ls-remote origin refs/heads/main | awk '{print $1}')"
  if [[ "$SHA" != "$REMOTE_SHA" ]]; then
    echo "Publishing requires latest origin/main: local=$SHA remote=$REMOTE_SHA" >&2
    exit 1
  fi
fi

# The existing builder edits icon/Info.plist and adds placeholder vendor files.
# Use a disposable clone so the user's checkout stays untouched.
WORK="$(mktemp -d -t factorios-local)"
trap 'rm -rf "$WORK"' EXIT
git clone --quiet --no-local "$ROOT" "$WORK/Source"
git -C "$WORK/Source" checkout --quiet --detach "$SHA"

echo "Building game-free FactoriOS template from $SHA"
bash "$ROOT/Tools/build_factorios_template.sh" "$WORK/Source"

python3 - "$ROOT/dist/FactoriOS-template.ipa" "$ROOT/dist/template-build.json" "$SHA" <<'PY'
import json
import pathlib
import sys
import zipfile

ipa, manifest, sha = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
assert ipa.is_file() and ipa.stat().st_size > 0, 'Missing or empty template IPA'
assert json.loads(manifest.read_text())['source_sha'] == sha, 'Commit mismatch in manifest'
with zipfile.ZipFile(ipa) as archive:
    assert archive.testzip() is None, 'Invalid IPA zip'
    assert not any('/FactorioData/' in n or '/FactorioGuest.framework/' in n
                   for n in archive.namelist()), 'Personal game data found in template'
print(f'Validated game-free template: {ipa} ({ipa.stat().st_size:,} bytes)')
PY

if (( PUBLISH )); then
  if ! gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
    gh release create "$TAG" --repo "$REPO" --target "$SHA" \
      --title "$TAG" --notes "Game-free FactoriOS template built locally from $SHA."
  fi
  gh release upload "$TAG" \
    "$ROOT/dist/FactoriOS-template.ipa" "$ROOT/dist/template-build.json" \
    --repo "$REPO" --clobber
  gh workflow run windows-companion.yml --repo "$REPO" --ref main -f source_ref=main
  echo "Release: https://github.com/$REPO/releases/tag/$TAG"
  echo "Companion build: https://github.com/$REPO/actions/workflows/windows-companion.yml"
else
  echo "Local template: $ROOT/dist/FactoriOS-template.ipa"
  echo 'Use --publish to upload the template and start a Windows companion build.'
fi
