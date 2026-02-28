#!/usr/bin/env python3
"""
League Guard (macOS/Linux/Windows)
Watches filesystem paths and launches an interruption scene when a keyword is detected.

Default macOS scene:
- Fade whole screen to white
- Fade in image (default: ~/Desktop/disappoint.JPG)
- Play soundtrack (default: ~/Desktop/C418 - Mice on Venus - Minecraft Volume Alpha.mp3)
- Keep focus lock for at least 60 seconds
- Show text: "dont forget who you are"

Usage:
  python3 league_guard.py --paths /Applications ~/Applications ~
  python3 league_guard.py --paths /tmp --keyword figma
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from pathlib import Path

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except Exception as e:
    raise SystemExit(
        "Missing dependency: watchdog\n"
        "Install with: python3 -m pip install watchdog\n"
        f"Details: {e}"
    )

PATTERN = re.compile(r"league\s*of\s*legends", re.IGNORECASE)


def build_pattern(keyword: str) -> re.Pattern[str]:
    k = keyword.strip().lower()
    # Default "lol-related" matcher (broader than exact phrase only).
    if k in {"league of legends", "lol", "league"}:
        return re.compile(r"(league\s*of\s*legends|leagueclient|riot\s*client|riot\s*games|\blol\b)", re.IGNORECASE)

    escaped = re.escape(keyword.strip())
    escaped = escaped.replace(r"\ ", r"\s*")
    return re.compile(escaped, re.IGNORECASE)


def normalize_path(p: str) -> str:
    if not p or not p.strip():
        return ""
    return str(Path(os.path.expanduser(p)).resolve())


def accessibility_granted() -> bool:
    if os.uname().sysname != "Darwin":
        return True
    try:
        lib = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except Exception:
        return False


def finder_automation_granted() -> bool:
    if os.uname().sysname != "Darwin":
        return True
    script = 'tell application "Finder" to get name of startup disk'
    try:
        out = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL)
        return bool(out.decode("utf-8", errors="ignore").strip())
    except Exception:
        return False


def prompt_open_setup_on_launch() -> bool:
    """Styled launch prompt matching Reclaim theme; returns True when user chooses Open Setup."""
    if os.uname().sysname != "Darwin":
        return False

    swift_code = r'''
import AppKit
import Foundation

let bone = NSColor(calibratedRed: 0xE8/255.0, green: 0xD8/255.0, blue: 0xC9/255.0, alpha: 1)
let mist = NSColor(calibratedRed: 0x4B/255.0, green: 0x60/255.0, blue: 0x7F/255.0, alpha: 1)

func lato(_ size: CGFloat, _ weight: NSFont.Weight = .regular) -> NSFont {
    if weight == .semibold, let f = NSFont(name: "Lato-Semibold", size: size) { return f }
    if weight == .bold, let f = NSFont(name: "Lato-Bold", size: size) { return f }
    if let f = NSFont(name: "Lato-Regular", size: size) { return f }
    return NSFont.systemFont(ofSize: size, weight: weight)
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let w = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 640, height: 260), styleMask: [.titled, .closable], backing: .buffered, defer: false)
w.center()
w.title = "Reclaim"
w.isReleasedWhenClosed = false
w.backgroundColor = bone
w.makeKeyAndOrderFront(nil)

let root = NSView(frame: w.contentView!.bounds)
root.wantsLayer = true
root.layer?.backgroundColor = bone.cgColor
root.autoresizingMask = [.width, .height]
w.contentView = root

let line1 = NSTextField(labelWithString: "Reclaim is running.")
line1.font = lato(36, .bold)
line1.textColor = mist
line1.frame = NSRect(x: 36, y: 160, width: 568, height: 44)
root.addSubview(line1)

let line2 = NSTextField(labelWithString: "Want to change your image/audio/settings?")
line2.font = lato(24, .semibold)
line2.textColor = mist.withAlphaComponent(0.95)
line2.frame = NSRect(x: 36, y: 112, width: 568, height: 36)
root.addSubview(line2)

class Handler: NSObject {
    @objc func openSetup() {
        print("OPEN_SETUP")
        fflush(stdout)
        NSApp.terminate(nil)
    }
    @objc func cont() {
        print("CONTINUE")
        fflush(stdout)
        NSApp.terminate(nil)
    }
}
let h = Handler()

func themedButton(_ title: String, x: CGFloat, action: Selector) -> NSButton {
    let b = NSButton(title: title, target: h, action: action)
    b.isBordered = false
    b.wantsLayer = true
    b.layer?.backgroundColor = mist.cgColor
    b.layer?.cornerRadius = 12
    b.contentTintColor = bone
    b.font = lato(18, .semibold)
    b.frame = NSRect(x: x, y: 34, width: 170, height: 44)
    return b
}

let continueBtn = themedButton("Continue", x: 280, action: #selector(Handler.cont))
let setupBtn = themedButton("Open Setup", x: 466, action: #selector(Handler.openSetup))
root.addSubview(continueBtn)
root.addSubview(setupBtn)

_ = NSEvent.addLocalMonitorForEvents(matching: [.keyDown]) { event in
    if event.keyCode == 53 { // esc
        h.cont(); return nil
    }
    if event.modifierFlags.contains(.command), event.charactersIgnoringModifiers?.lowercased() == "q" {
        h.cont(); return nil
    }
    return event
}

app.activate(ignoringOtherApps: true)
app.run()
'''

    try:
        cp = _run_compiled_swift(swift_code, wait=True, capture_output=True)
        out = (cp.stdout or "").strip()
        return "OPEN_SETUP" in out
    except Exception:
        return False


def show_preflight_screen(ax_ok: bool, finder_ok: bool) -> None:
    if os.uname().sysname != "Darwin":
        return
    swift_code = f'''
import AppKit
import Foundation

let axOK = {"true" if ax_ok else "false"}
let finderOK = {"true" if finder_ok else "false"}

func row(_ title: String, _ ok: Bool) -> String {{
    return "\\(ok ? \"✅\" : \"❌\") \\(title)"
}}

let msg = """
Reclaim Preflight

\\(row("Accessibility permission", axOK))
\\(row("Automation permission (Finder)", finderOK))

Enable missing permissions in:
System Settings → Privacy & Security

Reclaim will not start monitoring until both are green.
"""

let alert = NSAlert()
alert.messageText = "Reclaim Preflight"
alert.informativeText = msg
alert.addButton(withTitle: "Open Accessibility Settings")
alert.addButton(withTitle: "Open Automation Settings")
alert.addButton(withTitle: "Quit")

let response = alert.runModal()
if response == .alertFirstButtonReturn {{
    NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")!)
}} else if response == .alertSecondButtonReturn {{
    NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation")!)
}}
'''
    _run_compiled_swift(swift_code, wait=True)


def is_trigger(path: str) -> bool:
    name = os.path.basename(path)
    return bool(PATTERN.search(name))


def _swift_bin() -> str:
    for p in ("/usr/bin/swift", "/usr/bin/xcrun"):
        if os.path.exists(p):
            return p
    return "swift"


def _swiftc_bin() -> str:
    for p in ("/usr/bin/swiftc",):
        if os.path.exists(p):
            return p
    # xcrun swiftc fallback
    if os.path.exists("/usr/bin/xcrun"):
        return "/usr/bin/xcrun"
    return "swiftc"


def _run_compiled_swift(swift_code: str, *, wait: bool, capture_output: bool = False, env: dict | None = None):
    """Compile Swift snippet once (cached) and run binary to avoid SwiftFrontend runtime app."""
    cache_dir = Path.home() / ".reclaim" / "swift-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(swift_code.encode("utf-8")).hexdigest()[:16]
    src = cache_dir / f"{key}.swift"
    bin_path = cache_dir / f"{key}.bin"

    if not bin_path.exists():
        src.write_text(swift_code)
        swiftc = _swiftc_bin()
        if swiftc.endswith("xcrun"):
            cmd = [swiftc, "swiftc", str(src), "-O", "-o", str(bin_path)]
        else:
            cmd = [swiftc, str(src), "-O", "-o", str(bin_path)]
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    run_env = os.environ.copy()
    run_env["LSUIElement"] = "1"
    if env:
        run_env.update(env)

    if wait:
        return subprocess.run(
            [str(bin_path)],
            check=False,
            stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            env=run_env,
        )

    return subprocess.Popen(
        [str(bin_path)],
        stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        env=run_env,
    )


def start_interaction_monitor(overlay: "WarningOverlay", watch_paths: list[str]):
    """Native Swift accessibility watcher: frontmost app + focused window title."""
    if os.uname().sysname != "Darwin":
        return

    swift_code = r'''
import AppKit
import ApplicationServices
import Foundation

let pattern = try! NSRegularExpression(pattern: "(league\\s*of\\s*legends|leagueclient|riot\\s*client|riot\\s*games|\\blol\\b)", options: [.caseInsensitive])

func match(_ s: String) -> Bool {
    let range = NSRange(s.startIndex..<s.endIndex, in: s)
    return pattern.firstMatch(in: s, options: [], range: range) != nil
}

func focusedWindowTitle(pid: pid_t) -> String {
    let appElem = AXUIElementCreateApplication(pid)
    var focusedWin: CFTypeRef?
    let err1 = AXUIElementCopyAttributeValue(appElem, kAXFocusedWindowAttribute as CFString, &focusedWin)
    guard err1 == .success, let win = focusedWin else { return "" }

    var titleRef: CFTypeRef?
    let err2 = AXUIElementCopyAttributeValue(win as! AXUIElement, kAXTitleAttribute as CFString, &titleRef)
    if err2 == .success, let t = titleRef as? String { return t }
    return ""
}

func finderSelectionPath() -> String {
    let source = """
    tell application \"Finder\"
        if (count of selection) > 0 then
            set theItem to item 1 of (get selection)
            return POSIX path of (theItem as alias)
        end if
    end tell
    """
    var errorInfo: NSDictionary?
    guard let script = NSAppleScript(source: source) else { return "" }
    let result = script.executeAndReturnError(&errorInfo)
    if errorInfo != nil { return "" }
    return result.stringValue ?? ""
}

print("STATUS:WATCHER_STARTED")
fflush(stdout)

var lastHit = ""
var lastAt = Date(timeIntervalSince1970: 0)
var lastSelection = ""

while true {
    let frontApp = NSWorkspace.shared.frontmostApplication
    let appName = frontApp?.localizedName ?? ""
    let pid = frontApp?.processIdentifier ?? 0
    let title = pid > 0 ? focusedWindowTitle(pid: pid) : ""
    let combined = "\(appName) | \(title)"

    var hit = ""
    if match(combined) { hit = combined }

    if hit.isEmpty && appName == "Finder" {
        let sel = finderSelectionPath()
        if !sel.isEmpty && sel != lastSelection && match(sel) {
            hit = sel
        }
        if !sel.isEmpty { lastSelection = sel }
    }

    if !hit.isEmpty {
        let now = Date()
        if hit != lastHit || now.timeIntervalSince(lastAt) > 2.0 {
            print("HIT:\(hit)")
            fflush(stdout)
            lastHit = hit
            lastAt = now
        }
    }

    usleep(160_000)
}
'''

    def run_watcher():
        try:
            proc = _run_compiled_swift(swift_code, wait=False, capture_output=True)
        except Exception:
            return

        if not proc.stdout:
            return

        for line in proc.stdout:
            line = line.strip()
            if line.startswith("HIT:"):
                overlay.flash(line[4:].strip())

    threading.Thread(target=run_watcher, daemon=True).start()


def reclaim_config_path() -> Path:
    return Path.home() / ".reclaim" / "config.json"


def reclaim_open_setup_flag_path() -> Path:
    return Path.home() / ".reclaim" / "open-setup"


def load_reclaim_config() -> dict:
    p = reclaim_config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_reclaim_config(config: dict):
    p = reclaim_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2))


def run_first_time_setup(default_image: str, default_audio: str) -> dict:
    """Launches a simple 3-page macOS setup wizard and writes ~/.reclaim/config.json."""
    if os.uname().sysname != "Darwin":
        return {}

    config_file = str(reclaim_config_path())
    image_default = normalize_path(default_image).replace('"', '\\"')
    audio_default = normalize_path(default_audio).replace('"', '\\"')
    config_file_safe = config_file.replace('"', '\\"')

    swift_code = f'''
import AppKit
import Foundation

let configPath = "{config_file_safe}"
let defaultImage = "{image_default}"
let defaultAudio = "{audio_default}"

let bone = NSColor(calibratedRed: 0xE8/255.0, green: 0xD8/255.0, blue: 0xC9/255.0, alpha: 1)
let mist = NSColor(calibratedRed: 0x4B/255.0, green: 0x60/255.0, blue: 0x7F/255.0, alpha: 1)

func lato(_ size: CGFloat, _ weight: NSFont.Weight = .regular) -> NSFont {{
    if weight == .semibold, let f = NSFont(name: "Lato-Semibold", size: size) {{ return f }}
    if weight == .bold, let f = NSFont(name: "Lato-Bold", size: size) {{ return f }}
    if let f = NSFont(name: "Lato-Regular", size: size) {{ return f }}
    return NSFont.systemFont(ofSize: size, weight: weight)
}}

final class DropZone: NSView {{
    let title = NSTextField(labelWithString: "Drop file here or click this area")
    var onFile: ((String) -> Void)?
    var onClickPicker: (() -> Void)?
    private let dashLayer = CAShapeLayer()

    override init(frame frameRect: NSRect) {{
        super.init(frame: frameRect)
        wantsLayer = true
        layer?.backgroundColor = bone.withAlphaComponent(0.35).cgColor
        layer?.cornerRadius = 14

        dashLayer.strokeColor = mist.cgColor
        dashLayer.fillColor = NSColor.clear.cgColor
        dashLayer.lineWidth = 3.0
        dashLayer.lineDashPattern = [10, 8]
        layer?.addSublayer(dashLayer)

        registerForDraggedTypes([.fileURL, .URL, .string])

        title.font = lato(17, .semibold)
        title.textColor = mist
        title.alignment = .center
        title.frame = NSRect(x: 16, y: frameRect.height/2 - 14, width: frameRect.width - 32, height: 28)
        addSubview(title)
    }}

    required init?(coder: NSCoder) {{ fatalError() }}

    override func layout() {{
        super.layout()
        dashLayer.path = CGPath(roundedRect: bounds.insetBy(dx: 4, dy: 4), cornerWidth: 12, cornerHeight: 12, transform: nil)
    }}

    override func mouseDown(with event: NSEvent) {{
        onClickPicker?()
    }}

    override func draggingEntered(_ sender: NSDraggingInfo) -> NSDragOperation {{
        title.stringValue = "Release to drop file"
        return .copy
    }}

    override func draggingExited(_ sender: NSDraggingInfo?) {{
        title.stringValue = "Drop file here or click this area"
    }}

    override func performDragOperation(_ sender: NSDraggingInfo) -> Bool {{
        let p = sender.draggingPasteboard

        if let items = p.readObjects(forClasses: [NSURL.self], options: nil) as? [URL], let first = items.first {{
            onFile?(first.path)
            title.stringValue = "File selected"
            return true
        }}

        if let raw = p.string(forType: .fileURL), let url = URL(string: raw), url.isFileURL {{
            onFile?(url.path)
            title.stringValue = "File selected"
            return true
        }}

        title.stringValue = "Drop file here or click this area"
        return false
    }}
}}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let baseRect = NSRect(x: 0, y: 0, width: 780, height: 520)
let window = NSWindow(contentRect: baseRect, styleMask: [.titled, .closable, .fullSizeContentView], backing: .buffered, defer: false)
window.center()
window.isOpaque = true
window.backgroundColor = bone
window.hasShadow = true
window.titleVisibility = .hidden
window.titlebarAppearsTransparent = true
window.isMovableByWindowBackground = true
window.standardWindowButton(.miniaturizeButton)?.isHidden = true
window.standardWindowButton(.zoomButton)?.isHidden = true
window.makeKeyAndOrderFront(nil)

let root = NSView(frame: NSRect(origin: .zero, size: baseRect.size))
root.autoresizingMask = [.width, .height]
root.wantsLayer = true
root.layer?.backgroundColor = bone.cgColor
root.alphaValue = 0.0
window.contentView = root

func pageContainer() -> NSView {{
    let v = NSView(frame: root.bounds)
    v.autoresizingMask = [.width, .height]
    v.alphaValue = 0
    return v
}}

let p1 = pageContainer(); let p2 = pageContainer(); let p3 = pageContainer(); let p4 = pageContainer()
root.addSubview(p4); root.addSubview(p3); root.addSubview(p2); root.addSubview(p1)
p1.isHidden = false
p2.isHidden = true
p3.isHidden = true
p4.isHidden = true

var imageChoice = ""
var audioChoice = ""

let title1 = NSTextField(labelWithString: "reclaim")
title1.textColor = mist
title1.font = lato(72, .bold)
title1.alignment = .center
title1.frame = NSRect(x: 100, y: 240, width: 580, height: 100)
p1.addSubview(title1)

func arrowButton(x: CGFloat, y: CGFloat) -> NSButton {{
    let b = NSButton(title: "→", target: nil, action: nil)
    b.frame = NSRect(x: x, y: y, width: 72, height: 54)
    b.isBordered = false
    b.bezelStyle = .regularSquare
    b.wantsLayer = true
    b.layer?.backgroundColor = mist.cgColor
    b.layer?.cornerRadius = 12

    let p = NSMutableParagraphStyle()
    p.alignment = .center
    b.attributedTitle = NSAttributedString(
        string: "→",
        attributes: [
            .font: lato(34, .bold),
            .foregroundColor: bone,
            .paragraphStyle: p
        ]
    )
    return b
}}

let next1 = arrowButton(x: 340, y: 34)
next1.frame = NSRect(x: 340, y: 34, width: 100, height: 64)
let p1Style = NSMutableParagraphStyle(); p1Style.alignment = .center
next1.attributedTitle = NSAttributedString(string: "→", attributes: [.font: lato(42, .bold), .foregroundColor: bone, .paragraphStyle: p1Style])
p1.addSubview(next1)

let head2 = NSTextField(labelWithString: "choose an image to display")
head2.textColor = mist
head2.font = lato(34, .semibold)
head2.alignment = .center
head2.frame = NSRect(x: 80, y: 432, width: 620, height: 48)
p2.addSubview(head2)

let dzImage = DropZone(frame: NSRect(x: 150, y: 222, width: 480, height: 180))
let imagePathLabel = NSTextField(labelWithString: "No image selected")
imagePathLabel.alignment = .center
imagePathLabel.textColor = mist
imagePathLabel.font = lato(13, .regular)
imagePathLabel.frame = NSRect(x: 80, y: 188, width: 620, height: 24)
imagePathLabel.lineBreakMode = .byTruncatingMiddle
let imageConfirm = NSTextField(labelWithString: "")
imageConfirm.font = lato(14, .regular)
imageConfirm.textColor = mist
imageConfirm.alignment = .center
imageConfirm.frame = NSRect(x: 80, y: 160, width: 620, height: 24)

let next2 = arrowButton(x: 670, y: 24)
next2.isEnabled = false
next2.alphaValue = 0.35

p2.addSubview(dzImage); p2.addSubview(imagePathLabel); p2.addSubview(imageConfirm); p2.addSubview(next2)

let head3 = NSTextField(labelWithString: "choose a track to play")
head3.textColor = mist
head3.font = lato(34, .semibold)
head3.alignment = .center
head3.frame = NSRect(x: 80, y: 432, width: 620, height: 48)
p3.addSubview(head3)

let dzAudio = DropZone(frame: NSRect(x: 150, y: 222, width: 480, height: 180))
let audioPathLabel = NSTextField(labelWithString: "No audio selected")
audioPathLabel.alignment = .center
audioPathLabel.textColor = mist
audioPathLabel.font = lato(13, .regular)
audioPathLabel.frame = NSRect(x: 80, y: 188, width: 620, height: 24)
audioPathLabel.lineBreakMode = .byTruncatingMiddle
let audioConfirm = NSTextField(labelWithString: "")
audioConfirm.font = lato(14, .regular)
audioConfirm.textColor = mist
audioConfirm.alignment = .center
audioConfirm.frame = NSRect(x: 80, y: 160, width: 620, height: 24)

let finish3 = arrowButton(x: 670, y: 24)
finish3.isEnabled = false
finish3.alphaValue = 0.35

let setupDone = NSTextField(labelWithString: "setup complete.")
setupDone.textColor = mist
setupDone.font = lato(28, .semibold)
setupDone.alignment = .center
setupDone.frame = NSRect(x: 80, y: 280, width: 620, height: 40)

let closeHint = NSTextField(labelWithString: "you may close this window, reclaim will run in the background")
closeHint.textColor = mist.withAlphaComponent(0.9)
closeHint.font = lato(18, .regular)
closeHint.alignment = .center
closeHint.frame = NSRect(x: 60, y: 240, width: 660, height: 32)

p3.addSubview(dzAudio); p3.addSubview(audioPathLabel); p3.addSubview(audioConfirm); p3.addSubview(finish3)
p4.addSubview(setupDone); p4.addSubview(closeHint)

func transition(from: NSView, to: NSView) {{
    to.alphaValue = 0
    to.isHidden = false
    NSAnimationContext.runAnimationGroup {{ ctx in
        ctx.duration = 0.45
        from.animator().alphaValue = 0
        to.animator().alphaValue = 1
    }} completionHandler: {{
        from.isHidden = true
    }}
}}

class Handler: NSObject {{
    let fn: () -> Void
    init(_ fn: @escaping () -> Void) {{ self.fn = fn }}
    @objc func go() {{ fn() }}
}}

let hNext1 = Handler {{ transition(from: p1, to: p2) }}
next1.target = hNext1; next1.action = #selector(Handler.go)

dzImage.onClickPicker = {{
    let panel = NSOpenPanel()
    panel.canChooseFiles = true
    panel.canChooseDirectories = false
    panel.allowedFileTypes = ["png", "jpg", "jpeg", "heic", "webp", "gif"]
    if panel.runModal() == .OK, let url = panel.url {{
        imageChoice = url.path
        imagePathLabel.stringValue = imageChoice
        imageConfirm.stringValue = "Image selected. Looks good."
        next2.isEnabled = true
        next2.alphaValue = 1.0
    }}
}}

dzImage.onFile = {{ path in
    imageChoice = path
    imagePathLabel.stringValue = path
    imageConfirm.stringValue = "Image selected. Looks good."
    next2.isEnabled = true
        next2.alphaValue = 1.0
}}

let hNext2 = Handler {{ transition(from: p2, to: p3) }}
next2.target = hNext2; next2.action = #selector(Handler.go)

dzAudio.onClickPicker = {{
    let panel = NSOpenPanel()
    panel.canChooseFiles = true
    panel.canChooseDirectories = false
    panel.allowedFileTypes = ["mp3", "m4a", "wav", "aiff", "aac", "flac"]
    if panel.runModal() == .OK, let url = panel.url {{
        audioChoice = url.path
        audioPathLabel.stringValue = audioChoice
        audioConfirm.stringValue = "Track selected."
        finish3.isEnabled = true
        finish3.alphaValue = 1.0
    }}
}}

dzAudio.onFile = {{ path in
    audioChoice = path
    audioPathLabel.stringValue = path
    audioConfirm.stringValue = "Track selected."
    finish3.isEnabled = true
        finish3.alphaValue = 1.0
}}

let hFinish = Handler {{
    let obj: [String: Any] = [
        "setup_complete": true,
        "image_path": imageChoice,
        "audio_path": audioChoice,
        "scene_text": "dont forget who you are"
    ]
    let data = try! JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted])
    let cfgURL = URL(fileURLWithPath: configPath)
    try? FileManager.default.createDirectory(at: cfgURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    try? data.write(to: cfgURL)

    transition(from: p3, to: p4)
}}
finish3.target = hFinish; finish3.action = #selector(Handler.go)

p1.alphaValue = 1
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)
NSAnimationContext.runAnimationGroup {{ ctx in
    ctx.duration = 0.45
    root.animator().alphaValue = 1.0
}}

_ = NSEvent.addLocalMonitorForEvents(matching: [.keyDown]) {{ event in
    if event.modifierFlags.contains(.command), event.charactersIgnoringModifiers?.lowercased() == "q" {{
        NSApp.terminate(nil)
        return nil
    }}
    return event
}}

app.run()
'''

    _run_compiled_swift(swift_code, wait=True)
    return load_reclaim_config()


class WarningOverlay:
    def __init__(
        self,
        seconds: int = 4,
        lock_seconds: int = 60,
        image_path: str = "",
        audio_path: str = "",
        scene_text: str = "dont forget who you are",
        dev_exit: bool = False,
    ):
        self.seconds = seconds
        self.lock_seconds = lock_seconds
        self.image_path = normalize_path(image_path)
        self.audio_path = normalize_path(audio_path)
        self.scene_text = scene_text
        self.dev_exit = dev_exit

        self._lock = threading.Lock()
        self._last = 0.0

    def flash(self, reason: str):
        now = time.time()
        with self._lock:
            # Throttle repeated flashes if many events fire together
            if now - self._last < 2:
                return
            self._last = now

        threading.Thread(target=self._show, args=(reason,), daemon=True).start()

    def _show(self, reason: str):
        if os.uname().sysname == "Darwin":
            self._macos_scene(reason)
            return

        # Non-macOS fallback
        print(f"[WARNING] Triggered: {reason}")

    def _macos_scene(self, reason: str):
        image_path = self.image_path
        audio_path = self.audio_path
        lock_seconds = max(60, int(self.lock_seconds))

        if not os.path.exists(image_path):
            print(f"[WARNING] Image not found: {image_path}")
        if not os.path.exists(audio_path):
            print(f"[WARNING] Audio not found: {audio_path}")

        # Escape for embedding in Swift source literal
        safe_reason = reason.replace('"', '\\"')
        safe_text = self.scene_text.replace('"', '\\"')
        safe_image = image_path.replace('"', '\\"')
        safe_audio = audio_path.replace('"', '\\"')

        swift_code = '''
import AppKit
import Foundation
import AVFoundation

let app = NSApplication.shared
app.setActivationPolicy(.accessory)

let lockSeconds: TimeInterval = __LOCK_SECONDS__
let start = Date()
let sceneText = "__SCENE_TEXT__"
let devExitEnabled = (__DEV_EXIT__ == 1)
let triggerPath = "__REASON__"
let removeText = "please remove \\(triggerPath)"
let imagePath = "__IMAGE_PATH__"
let audioPath = "__AUDIO_PATH__"
let bone = NSColor(calibratedRed: 0xE8/255.0, green: 0xD8/255.0, blue: 0xC9/255.0, alpha: 1)
let mist = NSColor(calibratedRed: 0x4B/255.0, green: 0x60/255.0, blue: 0x7F/255.0, alpha: 1)

func lato(_ size: CGFloat, _ weight: NSFont.Weight = .regular) -> NSFont {
    if weight == .semibold, let f = NSFont(name: "Lato-Semibold", size: size) { return f }
    if weight == .bold, let f = NSFont(name: "Lato-Bold", size: size) { return f }
    if let f = NSFont(name: "Lato-Regular", size: size) { return f }
    return NSFont.systemFont(ofSize: size, weight: weight)
}

class LockWindow: NSWindow {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { true }
}

let screenFrame = NSScreen.main?.frame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
let window = LockWindow(
    contentRect: screenFrame,
    styleMask: [.borderless],
    backing: .buffered,
    defer: false
)
window.level = .screenSaver
window.collectionBehavior = [.canJoinAllSpaces, .fullScreenPrimary]
window.backgroundColor = bone.withAlphaComponent(0.0)
window.isOpaque = false
window.ignoresMouseEvents = false
window.makeKeyAndOrderFront(nil)

let content = NSView(frame: screenFrame)
content.wantsLayer = true
content.layer?.backgroundColor = bone.withAlphaComponent(0.0).cgColor
window.contentView = content

let imageView = NSImageView(frame: NSRect(x: screenFrame.width * 0.2, y: screenFrame.height * 0.33, width: screenFrame.width * 0.6, height: screenFrame.height * 0.45))
imageView.imageScaling = .scaleProportionallyUpOrDown
imageView.alphaValue = 0.0
if FileManager.default.fileExists(atPath: imagePath), let img = NSImage(contentsOfFile: imagePath) {
    imageView.image = img
}
content.addSubview(imageView)

let text = NSTextField(labelWithString: sceneText)
text.textColor = mist.withAlphaComponent(0.0)
text.alignment = .center
text.font = lato(36, .semibold)
text.frame = NSRect(x: 80, y: screenFrame.height * 0.18, width: screenFrame.width - 160, height: 70)
content.addSubview(text)

let subtitle = NSTextField(labelWithString: removeText)
subtitle.textColor = mist.withAlphaComponent(0.0)
subtitle.alignment = .center
subtitle.font = lato(17, .regular)
subtitle.frame = NSRect(x: 80, y: screenFrame.height * 0.14, width: screenFrame.width - 160, height: 40)
subtitle.lineBreakMode = .byTruncatingMiddle
content.addSubview(subtitle)

let ringRect = NSRect(x: screenFrame.width - 120, y: screenFrame.height - 128, width: 92, height: 92)
let ringTrack = CAShapeLayer()
ringTrack.path = CGPath(ellipseIn: ringRect, transform: nil)
ringTrack.fillColor = NSColor.clear.cgColor
ringTrack.strokeColor = mist.withAlphaComponent(0.24).cgColor
ringTrack.lineWidth = 7

let ringProgress = CAShapeLayer()
ringProgress.path = CGPath(ellipseIn: ringRect, transform: nil)
ringProgress.fillColor = NSColor.clear.cgColor
ringProgress.strokeColor = mist.withAlphaComponent(0.92).cgColor
ringProgress.lineWidth = 7
ringProgress.lineCap = .round
ringProgress.strokeStart = 0
ringProgress.strokeEnd = 1

content.layer?.addSublayer(ringTrack)
content.layer?.addSublayer(ringProgress)

let hint = NSTextField(labelWithString: "")
hint.isHidden = true

let devExitButton = NSButton(title: "", target: nil, action: nil)
devExitButton.frame = NSRect(x: 28, y: screenFrame.height - 76, width: 170, height: 40)
devExitButton.isBordered = false
devExitButton.wantsLayer = true
devExitButton.alphaValue = 0.01
if let layer = devExitButton.layer {
    layer.backgroundColor = NSColor.clear.cgColor
    layer.cornerRadius = 8
}
if devExitEnabled {
    content.addSubview(devExitButton)
}

let minuteExitButton = NSButton(title: "", target: nil, action: nil)
minuteExitButton.frame = NSRect(x: 24, y: screenFrame.height - 70, width: 42, height: 42)
minuteExitButton.isBordered = false
minuteExitButton.wantsLayer = true
minuteExitButton.layer?.backgroundColor = mist.withAlphaComponent(0.18).cgColor
minuteExitButton.layer?.cornerRadius = 21
minuteExitButton.contentTintColor = mist
let xStyle = NSMutableParagraphStyle(); xStyle.alignment = .center
minuteExitButton.attributedTitle = NSAttributedString(
    string: "×",
    attributes: [
        .font: lato(26, .bold),
        .foregroundColor: mist,
        .paragraphStyle: xStyle,
        .baselineOffset: 0.8
    ]
)
minuteExitButton.alphaValue = 0.0
content.addSubview(minuteExitButton)

var player: AVAudioPlayer?
if FileManager.default.fileExists(atPath: audioPath) {
    do {
        player = try AVAudioPlayer(contentsOf: URL(fileURLWithPath: audioPath))
        player?.prepareToPlay()
        player?.play()
    } catch {
        print("Audio error: \\(error)")
    }
}

let totalDuration = max(1.0, player?.duration ?? lockSeconds)
let autoEndAfter = totalDuration
var unlocked = false
var minuteExitShown = false

func revealTriggerPath() {
    if triggerPath.hasPrefix("/") {
        if FileManager.default.fileExists(atPath: triggerPath) {
            NSWorkspace.shared.selectFile(triggerPath, inFileViewerRootedAtPath: "")
            return
        }
        let dir = (triggerPath as NSString).deletingLastPathComponent
        if !dir.isEmpty {
            NSWorkspace.shared.open(URL(fileURLWithPath: dir))
        }
    }
}

class ExitHandler: NSObject {
    let onExit: () -> Void
    init(onExit: @escaping () -> Void) { self.onExit = onExit }
    @objc func tap() { onExit() }
}

let exitHandler = ExitHandler {
    player?.stop()
    revealTriggerPath()
    NSApp.presentationOptions = []
    app.terminate(nil)
}
devExitButton.target = exitHandler
devExitButton.action = #selector(ExitHandler.tap)
minuteExitButton.target = exitHandler
minuteExitButton.action = #selector(ExitHandler.tap)

var clickMonitor: Any?
clickMonitor = NSEvent.addLocalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown]) { event in
    // Always allow dev-exit button clicks through, even while locked.
    let inWindow = window.convertPoint(fromScreen: event.locationInWindow)
    let inContent = content.convert(inWindow, from: nil)
    if devExitEnabled && devExitButton.frame.contains(inContent) {
        return event
    }
    if minuteExitButton.alphaValue > 0.01 && minuteExitButton.frame.contains(inContent) {
        return event
    }

    if unlocked {
        exitHandler.tap()
        return nil
    }
    // Locked: swallow all other clicks.
    return nil
}

var keyMonitor: Any?
keyMonitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown]) { event in
    if event.modifierFlags.contains(.command), event.charactersIgnoringModifiers?.lowercased() == "q" {
        exitHandler.tap()
        return nil
    }
    return event
}

app.activate(ignoringOtherApps: true)
window.orderFrontRegardless()

NSApp.presentationOptions = [
    .hideDock,
    .disableProcessSwitching,
    .disableForceQuit,
    .disableSessionTermination,
    .disableHideApplication,
    .autoHideMenuBar,
    .autoHideToolbar
]

NSAnimationContext.runAnimationGroup { ctx in
    ctx.duration = 3.0
    content.animator().layer?.backgroundColor = bone.withAlphaComponent(1.0).cgColor
}

DispatchQueue.main.asyncAfter(deadline: .now() + 1.8) {
    NSAnimationContext.runAnimationGroup { ctx in
        ctx.duration = 2.8
        imageView.animator().alphaValue = 1.0
        text.animator().textColor = mist.withAlphaComponent(1.0)
        subtitle.animator().textColor = mist.withAlphaComponent(0.75)
        hint.animator().textColor = mist.withAlphaComponent(0.45)
    }
}

let focusTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { timer in
    let elapsed = Date().timeIntervalSince(start)
    let remainingSeconds = max(0, Int(ceil(totalDuration - elapsed)))
    let progress = max(0.0, min(1.0, (totalDuration - elapsed) / totalDuration))
    ringProgress.strokeEnd = CGFloat(progress)

    if !minuteExitShown && elapsed >= 60 {
        minuteExitShown = true
        NSAnimationContext.runAnimationGroup { ctx in
            ctx.duration = 0.35
            minuteExitButton.animator().alphaValue = 0.92
        }
    }

    if !unlocked {
        app.activate(ignoringOtherApps: true)
        window.orderFrontRegardless()
        if remainingSeconds > 0 {
            hint.stringValue = "overlay unlocks when song ends"
        } else {
            unlocked = true
            hint.stringValue = "click anywhere to dismiss"
            NSAnimationContext.runAnimationGroup { ctx in
                ctx.duration = 0.25
                hint.animator().textColor = NSColor.black.withAlphaComponent(0.65)
            }
        }
    }

    if elapsed >= autoEndAfter {
        timer.invalidate()
        if let monitor = clickMonitor { NSEvent.removeMonitor(monitor) }
        if let k = keyMonitor { NSEvent.removeMonitor(k) }
        revealTriggerPath()
        player?.stop()
        NSApp.presentationOptions = []
        app.terminate(nil)
    }
}

RunLoop.current.add(focusTimer, forMode: .common)
app.run()
'''

        swift_code = (
            swift_code
            .replace("__LOCK_SECONDS__", str(lock_seconds))
            .replace("__SCENE_TEXT__", safe_text)
            .replace("__DEV_EXIT__", "1" if self.dev_exit else "0")
            .replace("__REASON__", safe_reason)
            .replace("__IMAGE_PATH__", safe_image)
            .replace("__AUDIO_PATH__", safe_audio)
        )

        try:
            _run_compiled_swift(swift_code, wait=False)
        except Exception as ex:
            print(f"[WARNING] Could not launch Swift scene: {ex}")


class LoLHandler(FileSystemEventHandler):
    def __init__(self, overlay: WarningOverlay):
        super().__init__()
        self.overlay = overlay

    def on_any_event(self, event):
        # Check both source and destination paths when available
        paths = [getattr(event, "src_path", "")]
        if hasattr(event, "dest_path"):
            paths.append(getattr(event, "dest_path", ""))

        for p in paths:
            if p and is_trigger(p):
                print(f"Trigger matched: {p}")
                self.overlay.flash(p)
                break


def initial_scan(paths: list[str], overlay: WarningOverlay):
    for root in paths:
        for dirpath, dirnames, filenames in os.walk(root):
            for n in dirnames + filenames:
                if PATTERN.search(n):
                    overlay.flash(os.path.join(dirpath, n))
                    return


def find_any_matching_path(paths: list[str]) -> str:
    # Fast local walk in watched paths
    for root in paths:
        for dirpath, dirnames, filenames in os.walk(root):
            for n in dirnames + filenames:
                if PATTERN.search(n):
                    return os.path.join(dirpath, n)

    # Fallback global Spotlight scan (macOS)
    if os.uname().sysname == "Darwin":
        try:
            out = subprocess.check_output(
                ["mdfind", "kMDItemFSName == '*league*of*legends*'c || kMDItemFSName == '*leagueclient*'c || kMDItemFSName == '*riot*client*'c || kMDItemFSName == '*riot*games*'c"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="ignore")
            for p in out.splitlines():
                p = p.strip()
                if p and os.path.exists(p) and PATTERN.search(os.path.basename(p)):
                    return p
        except Exception:
            pass

    return ""


def startup_spotlight_scan(overlay: WarningOverlay):
    p = find_any_matching_path([])
    if p:
        overlay.flash(p)


def start_nag_mode(overlay: WarningOverlay, paths: list[str], every_seconds: int = 300):
    def loop():
        while True:
            hit = find_any_matching_path(paths)
            if hit:
                overlay.flash(hit)
            time.sleep(max(30, every_seconds))

    threading.Thread(target=loop, daemon=True).start()


def main():
    global PATTERN

    parser = argparse.ArgumentParser(description="Launch interruption scene if keyword appears in filenames.")
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["/Applications", "~/Applications", "~", "/tmp", "/private/tmp"],
        help="Paths to watch recursively.",
    )
    parser.add_argument("--flash-seconds", type=int, default=4, help="Legacy value (kept for compatibility).")
    parser.add_argument("--keyword", default="league of legends", help="Keyword to detect in file/folder names.")
    parser.add_argument("--lock-seconds", type=int, default=60, help="Minimum lock duration for macOS scene.")
    parser.add_argument("--image-path", default="", help="Image to fade in on macOS scene.")
    parser.add_argument("--audio-path", default="", help="Audio to play on macOS scene.")
    parser.add_argument("--scene-text", default="dont forget who you are", help="Text shown under the image.")
    parser.add_argument("--dev-exit", action="store_true", help="Enable hidden developer exit hotspot (disable for public builds).")
    parser.add_argument("--setup", action="store_true", help="Force open setup wizard on launch.")
    parser.add_argument("--reset-setup", action="store_true", help="Delete saved setup config, then open setup wizard.")
    args = parser.parse_args()

    PATTERN = build_pattern(args.keyword)

    watch_paths = [normalize_path(p) for p in args.paths]
    watch_paths = [p for p in watch_paths if os.path.exists(p)]

    if not watch_paths:
        raise SystemExit("No valid watch paths found.")

    # Preflight is not required for filesystem scan mode.
    if args.reset_setup:
        try:
            reclaim_config_path().unlink(missing_ok=True)
        except Exception:
            pass

    config = load_reclaim_config()
    open_setup_flag = reclaim_open_setup_flag_path().exists()
    launch_prompt_setup = bool(config.get("setup_complete")) and prompt_open_setup_on_launch()
    should_open_setup = args.setup or args.reset_setup or open_setup_flag or launch_prompt_setup or (os.uname().sysname == "Darwin" and not config.get("setup_complete"))

    if should_open_setup:
        print("Opening Reclaim setup...")
        config = run_first_time_setup(args.image_path, args.audio_path)
        try:
            reclaim_open_setup_flag_path().unlink(missing_ok=True)
        except Exception:
            pass

    final_image = config.get("image_path", args.image_path)
    final_audio = config.get("audio_path", args.audio_path)
    final_text = config.get("scene_text", args.scene_text)

    overlay = WarningOverlay(
        seconds=args.flash_seconds,
        lock_seconds=args.lock_seconds,
        image_path=final_image,
        audio_path=final_audio,
        scene_text=final_text,
        dev_exit=args.dev_exit,
    )
    # Filesystem-scan mode (trigger when matching file/folder is detected).
    handler = LoLHandler(overlay)
    observer = Observer()

    for p in watch_paths:
        observer.schedule(handler, p, recursive=True)
        print(f"Watching: {p}")

    # Trigger immediately if matching file already exists.
    initial_scan(watch_paths, overlay)
    startup_spotlight_scan(overlay)

    observer.start()
    start_nag_mode(overlay, watch_paths, every_seconds=1800)
    print("Reclaim is running. Press Ctrl+C to stop.")
    print("Filesystem scan mode enabled: triggers on matching file/folder detection.")
    print("Nag mode enabled: retriggers every 30 minutes until matching files are removed.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()

if __name__ == "__main__":
    main()
