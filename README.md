# Reclaim

Reclaim is a macOS app that detects League-related files and triggers an intervention overlay.

## Run (dev)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install watchdog pyinstaller
python league_guard.py
```

## Build app
```bash
source .venv/bin/activate
pyinstaller --noconfirm --windowed --icon Reclaim.icns --name Reclaim league_guard.py
```

## Build DMG
```bash
bash scripts/build_dmg.sh
```

See `Reclaim_RELEASE.md` for release checklist.
