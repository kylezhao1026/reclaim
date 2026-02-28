#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/kylezhao/.openclaw/workspace"
APP="$ROOT/dist/Reclaim.app"
DMG="$ROOT/dist/Reclaim.dmg"
STAGE="$ROOT/dist/dmg-stage"

if [[ ! -d "$APP" ]]; then
  echo "Missing $APP. Build app first with pyinstaller."
  exit 1
fi

rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/Reclaim.app"
ln -s /Applications "$STAGE/Applications"

hdiutil create -volname "Reclaim" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"

echo "Created: $DMG"
