# Reclaim

A focused macOS intervention app for reducing League of Legends relapse loops.

Reclaim watches for LoL-related files and, when triggered, shows a full-screen interruption experience (custom image + music + countdown ring) to break autopilot behavior.

---

## ✨ What Reclaim Does

- Detects League-related files/folders (filesystem scan mode)
- Launches a full-screen intervention overlay
- Uses your chosen image + audio track
- Shows a circular time-progress indicator
- Supports recurring reminders (nag mode)
- Includes first-run setup + re-setup flow

---

## 🚀 Quick Start (Development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install watchdog pyinstaller
python league_guard.py
```

---

## 🛠 Build the macOS App

```bash
source .venv/bin/activate
pyinstaller --noconfirm --windowed --icon Reclaim.icns --name Reclaim league_guard.py
```

Output:
- `dist/Reclaim.app`

---

## 📦 Build a DMG

```bash
bash scripts/build_dmg.sh
```

Output:
- `dist/Reclaim.dmg`

---

## ⚙️ Re-open Setup

If setup is already complete and you want to reconfigure:

```bash
/Applications/Reclaim.app/Contents/MacOS/Reclaim --setup
```

Or reset fully:

```bash
/Applications/Reclaim.app/Contents/MacOS/Reclaim --reset-setup
```

---

## 🧭 Project Status

Reclaim is actively evolving. UX and behavior are being tuned in rapid iterations.
