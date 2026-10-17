#!/bin/bash
# Build only the iOS wrapper. Purchased Factorio files stay on the user's computer.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$(cd "${1:?Pass the selected source checkout.}" && pwd)"
WORK="$(mktemp -d "${RUNNER_TEMP:-/tmp}/factorios-template.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

ICON="$SOURCE/FactorioPad/Assets.xcassets/AppIcon.appiconset/icon.png"
sips -z 1024 1024 "$ROOT/Branding/icon.png" --out "$ICON" >/dev/null
PLIST="$SOURCE/FactorioPad/Info.plist"
/usr/libexec/PlistBuddy -c 'Set :CFBundleDisplayName FactoriOS' "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c 'Add :CFBundleDisplayName string FactoriOS' "$PLIST"

GUEST="$SOURCE/Vendor/FactorioGuest.framework"
DATA="$SOURCE/Vendor/FactorioData"
mkdir -p "$GUEST" "$DATA/base/scenarios/freeplay" "$DATA/core"
printf 'placeholder' > "$GUEST/FactorioGuest"
chmod +x "$GUEST/FactorioGuest"
python3 - "$GUEST/Info.plist" <<'PY'
import plistlib, sys
from pathlib import Path
Path(sys.argv[1]).write_bytes(plistlib.dumps({
    'CFBundleExecutable': 'FactorioGuest', 'CFBundleIdentifier': 'pl.adrian.FactorioPad.FactorioGuest',
    'CFBundleInfoDictionaryVersion': '6.0', 'CFBundleName': 'FactorioGuest',
    'CFBundlePackageType': 'FMWK', 'CFBundleShortVersionString': '0',
    'CFBundleVersion': '1', 'MinimumOSVersion': '17.0',
}))
PY
printf 'placeholder' > "$DATA/cacert.pem"
printf '{}\n' > "$DATA/base/info.json"
printf '{}\n' > "$DATA/core/info.json"
touch "$DATA/base/scenarios/freeplay/control.lua"

xcodebuild -project "$SOURCE/FactorioPad.xcodeproj" -scheme FactorioPad \
    -configuration Release -destination 'generic/platform=iOS' \
    -derivedDataPath "$WORK/DerivedData" CODE_SIGNING_ALLOWED=NO build
PRODUCT="$WORK/DerivedData/Build/Products/Release-iphoneos/FactorioPad.app"
test -f "$PRODUCT/FactorioPad"
mkdir -p "$WORK/Payload"
mv "$PRODUCT" "$WORK/Payload/FactorioPad.app"
rm -rf "$WORK/Payload/FactorioPad.app/FactorioData" \
       "$WORK/Payload/FactorioPad.app/Frameworks/FactorioGuest.framework"
/usr/bin/ditto --norsrc --noextattr -c -k --keepParent "$WORK/Payload" "$WORK/wrapper.ipa"
mkdir -p "$ROOT/dist"
python3 "$SOURCE/Tools/package_ipa.py" template "$WORK/wrapper.ipa" "$ROOT/dist/FactoriOS-template.ipa"
python3 - "$ROOT/dist/FactoriOS-template.ipa" <<'PY'
import json, sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    assert archive.testzip() is None
    assert not any('/FactorioData/' in n or '/FactorioGuest.framework/' in n for n in archive.namelist())
    markers = [n for n in archive.namelist() if n.endswith('/FactorioPadTemplate.json')]
    assert len(markers) == 1 and json.loads(archive.read(markers[0])) == {'format': 2}
PY
python3 - "$SOURCE" "$ROOT/dist/template-build.json" <<'PY'
import json, subprocess, sys
from pathlib import Path
sha = subprocess.check_output(['git', '-C', sys.argv[1], 'rev-parse', 'HEAD'], text=True).strip()
Path(sys.argv[2]).write_text(json.dumps({'source_sha': sha}, indent=2) + '\n')
PY
