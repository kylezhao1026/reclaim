# Reclaim release checklist

## Before sharing
- [ ] Build app bundle
- [ ] Ensure `--dev-exit` is **OFF** (default)
- [ ] Test setup wizard from clean state (`rm -f ~/.reclaim/config.json`)
- [ ] Test trigger in `/tmp`
- [ ] Create DMG package
- [ ] Code sign app + DMG
- [ ] Notarize and staple

## Build local app
```bash
cd /Users/kylezhao/.openclaw/workspace
source .venv/bin/activate
pyinstaller --noconfirm --windowed --icon Reclaim.icns --name Reclaim league_guard.py
```

## Build DMG
```bash
bash /Users/kylezhao/.openclaw/workspace/scripts/build_dmg.sh
```

Output:
- `dist/Reclaim.app`
- `dist/Reclaim.dmg`

## Notes
- For public release, app should be signed/notarized to avoid Gatekeeper warnings.
- Hidden dev-exit hotspot is only enabled when launched with `--dev-exit`.
