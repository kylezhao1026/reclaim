# Reclaim

Reclaim is a macOS app that helps interrupt League of Legends relapse loops with a full-screen intervention overlay.

## 📥 Download & Install

1. Go to **Releases**: https://github.com/kylezhao1026/reclaim/releases
2. Download the latest `Reclaim.dmg`
3. Open the DMG and drag **Reclaim.app** into **Applications**
4. Launch **Reclaim** from Applications

## ✅ First Launch

- Complete setup:
  - choose your image
  - choose your audio track
- Reclaim then runs in the background and watches for League-related files.

## ⚙️ Re-open Setup Later

When Reclaim starts, choose **Open Setup** if you want to change settings.

## 🚨 Trigger Behavior

- Reclaim triggers an overlay when matching League-related files are detected.
- It can retrigger on nag intervals if files remain.

## ❓Troubleshooting

- If Reclaim doesn’t appear to launch, check Activity Monitor for `Reclaim` process.
- If macOS blocks first launch, use:
  - right-click app → **Open**
  - or System Settings → Privacy & Security → **Open Anyway**

---

For contributors/devs, build and packaging details are in `Reclaim_RELEASE.md`.
