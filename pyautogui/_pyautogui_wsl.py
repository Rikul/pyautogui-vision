# Windows Subsystem for Linux (WSL) implementation of PyAutoGUI functions.
# Bridges mouse, keyboard, and screen operations from WSL to the Windows host desktop
# via a persistent PowerShell + Win32 P/Invoke helper process.
# BSD license

import atexit
import base64
import os
import shutil
import subprocess
import sys
import tempfile
import threading

import pyautogui
from pyautogui import LEFT, MIDDLE, RIGHT

if sys.platform in ("darwin", "win32"):
    raise Exception("The pyautogui_wsl module should only be loaded on a Linux/WSL system.")


_PS_BRIDGE_SCRIPT = r"""
Add-Type -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

public static class Win32Bridge {
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll")]
    public static extern bool SetProcessDPIAware();

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT lpPoint);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    public static extern int GetSystemMetrics(int nIndex);

    [DllImport("user32.dll")]
    public static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, UIntPtr dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern short VkKeyScanW(char ch);

    public static void CaptureScreen(string path, int x, int y, int width, int height) {
        using (Bitmap bmp = new Bitmap(width, height, PixelFormat.Format24bppRgb)) {
            using (Graphics g = Graphics.FromImage(bmp)) {
                g.CopyFromScreen(x, y, 0, 0, new Size(width, height), CopyPixelOperation.SourceCopy);
            }
            bmp.Save(path, ImageFormat.Png);
        }
    }
}
"@ -ReferencedAssemblies System.Drawing

[void][Win32Bridge]::SetProcessDPIAware()
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output "READY"

while ($null -ne ($line = [Console]::In.ReadLine())) {
    $parts = $line.Split(' ')
    $cmd = $parts[0]
    try {
        switch ($cmd) {
            "POS" {
                $pt = New-Object Win32Bridge+POINT
                [void][Win32Bridge]::GetCursorPos([ref]$pt)
                Write-Output "$($pt.X) $($pt.Y)"
            }
            "SIZE" {
                $w = [Win32Bridge]::GetSystemMetrics(0)
                $h = [Win32Bridge]::GetSystemMetrics(1)
                Write-Output "$w $h"
            }
            "SWAP" {
                $s = [Win32Bridge]::GetSystemMetrics(23)
                Write-Output "$s"
            }
            "MOVE" {
                [void][Win32Bridge]::SetCursorPos([int]$parts[1], [int]$parts[2])
                Write-Output "OK"
            }
            "MOUSE" {
                $ev = [uint32]$parts[1]
                $x = [int]$parts[2]
                $y = [int]$parts[3]
                $data = [int]$parts[4]
                $w = [Win32Bridge]::GetSystemMetrics(0)
                $h = [Win32Bridge]::GetSystemMetrics(1)
                $cx = [int]([math]::Floor(65536 * $x / $w) + 1)
                $cy = [int]([math]::Floor(65536 * $y / $h) + 1)
                [Win32Bridge]::mouse_event($ev, $cx, $cy, $data, [UIntPtr]::Zero)
                Write-Output "OK"
            }
            "KEY" {
                $vk = [byte][int]$parts[1]
                $flags = [uint32]$parts[2]
                [Win32Bridge]::keybd_event($vk, 0, $flags, [UIntPtr]::Zero)
                Write-Output "OK"
            }
            "VKSCAN" {
                $code = [int]$parts[1]
                $res = [Win32Bridge]::VkKeyScanW([char]$code)
                Write-Output "$res"
            }
            "SCREENSHOT" {
                $x = [int]$parts[1]
                $y = [int]$parts[2]
                $w = [int]$parts[3]
                $h = [int]$parts[4]
                $path = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($parts[5]))
                [Win32Bridge]::CaptureScreen($path, $x, $y, $w, $h)
                Write-Output "OK"
            }
            "QUIT" {
                break
            }
            default {
                Write-Output "ERR Unknown command: $cmd"
            }
        }
    } catch {
        Write-Output "ERR $($_.Exception.Message)"
    }
}
"""

# Win32 mouse_event constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_LEFTCLICK = MOUSEEVENTF_LEFTDOWN + MOUSEEVENTF_LEFTUP
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_RIGHTCLICK = MOUSEEVENTF_RIGHTDOWN + MOUSEEVENTF_RIGHTUP
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_MIDDLECLICK = MOUSEEVENTF_MIDDLEDOWN + MOUSEEVENTF_MIDDLEUP
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000

# Win32 keybd_event constants
KEYEVENTF_KEYDOWN = 0x0000
KEYEVENTF_KEYUP = 0x0002


def _find_powershell():
    """Find powershell.exe on the WSL PATH or standard Windows mount locations."""
    ps = shutil.which("powershell.exe")
    if ps:
        return ps
    candidates = [
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0/powershell.exe",
    ]
    for path in candidates:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise pyautogui.PyAutoGUIException(
        "PyAutoGUI detected WSL, but could not find powershell.exe to bridge to the Windows host. "
        "Ensure WSL Windows interop is enabled and /mnt/c/Windows/System32/WindowsPowerShell/v1.0 is accessible."
    )


class _WSLHostBridge(object):
    """Manages a persistent PowerShell child process for low-latency Win32 API calls from WSL."""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()

    def _ensure_proc(self):
        if self._proc is not None and self._proc.poll() is None:
            return
        ps_exe = _find_powershell()
        self._proc = subprocess.Popen(
            [ps_exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _PS_BRIDGE_SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1,
        )
        ready_line = self._proc.stdout.readline().strip()
        if ready_line != "READY":
            stderr_out = ""
            if self._proc.poll() is not None and self._proc.stderr:
                stderr_out = self._proc.stderr.read()
            raise pyautogui.PyAutoGUIException(
                "Failed to initialize WSL Windows host bridge (got %r). %s" % (ready_line, stderr_out)
            )

    def request(self, cmd):
        with self._lock:
            self._ensure_proc()
            self._proc.stdin.write(cmd + "\n")
            self._proc.stdin.flush()
            resp = self._proc.stdout.readline().strip()
            if resp.startswith("ERR "):
                raise pyautogui.PyAutoGUIException("WSL bridge error: %s" % resp[4:])
            return resp

    def close(self):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.stdin.write("QUIT\n")
                    self._proc.stdin.flush()
                    self._proc.terminate()
                except Exception:
                    pass
                self._proc = None


_bridge = _WSLHostBridge()
atexit.register(_bridge.close)


# Static Win32 virtual key mapping (matches _pyautogui_win.py without requiring ctypes.windll at import time)
keyboardMapping = dict([(key, None) for key in pyautogui.KEY_NAMES])
keyboardMapping.update({
    "backspace": 0x08,
    "\b": 0x08,
    "super": 0x5B,
    "tab": 0x09,
    "\t": 0x09,
    "clear": 0x0C,
    "enter": 0x0D,
    "\n": 0x0D,
    "\r": 0x0D,
    "return": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "pause": 0x13,
    "capslock": 0x14,
    "kana": 0x15,
    "hanguel": 0x15,
    "hangul": 0x15,
    "junja": 0x17,
    "final": 0x18,
    "hanja": 0x19,
    "kanji": 0x19,
    "esc": 0x1B,
    "escape": 0x1B,
    "convert": 0x1C,
    "nonconvert": 0x1D,
    "accept": 0x1E,
    "modechange": 0x1F,
    " ": 0x20,
    "space": 0x20,
    "pgup": 0x21,
    "pgdn": 0x22,
    "pageup": 0x21,
    "pagedown": 0x22,
    "end": 0x23,
    "home": 0x24,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "select": 0x29,
    "print": 0x2A,
    "execute": 0x2B,
    "prtsc": 0x2C,
    "prtscr": 0x2C,
    "prntscrn": 0x2C,
    "printscreen": 0x2C,
    "insert": 0x2D,
    "del": 0x2E,
    "delete": 0x2E,
    "help": 0x2F,
    "win": 0x5B,
    "winleft": 0x5B,
    "winright": 0x5C,
    "apps": 0x5D,
    "sleep": 0x5F,
    "num0": 0x60,
    "num1": 0x61,
    "num2": 0x62,
    "num3": 0x63,
    "num4": 0x64,
    "num5": 0x65,
    "num6": 0x66,
    "num7": 0x67,
    "num8": 0x68,
    "num9": 0x69,
    "multiply": 0x6A,
    "add": 0x6B,
    "separator": 0x6C,
    "subtract": 0x6D,
    "decimal": 0x6E,
    "divide": 0x6F,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
    "f13": 0x7C,
    "f14": 0x7D,
    "f15": 0x7E,
    "f16": 0x7F,
    "f17": 0x80,
    "f18": 0x81,
    "f19": 0x82,
    "f20": 0x83,
    "f21": 0x84,
    "f22": 0x85,
    "f23": 0x86,
    "f24": 0x87,
    "numlock": 0x90,
    "scrolllock": 0x91,
    "shiftleft": 0xA0,
    "shiftright": 0xA1,
    "ctrlleft": 0xA2,
    "ctrlright": 0xA3,
    "altleft": 0xA4,
    "altright": 0xA5,
    "browserback": 0xA6,
    "browserforward": 0xA7,
    "browserrefresh": 0xA8,
    "browserstop": 0xA9,
    "browsersearch": 0xAA,
    "browserfavorites": 0xAB,
    "browserhome": 0xAC,
    "volumemute": 0xAD,
    "volumedown": 0xAE,
    "volumeup": 0xAF,
    "nexttrack": 0xB0,
    "prevtrack": 0xB1,
    "stop": 0xB2,
    "playpause": 0xB3,
    "launchmail": 0xB4,
    "launchmediaselect": 0xB5,
    "launchapp1": 0xB6,
    "launchapp2": 0xB7,
})

# Populate standard US QWERTY printable ASCII VK codes statically so importing doesn't require round-trips.
for _c in range(ord("0"), ord("9") + 1):
    keyboardMapping[chr(_c)] = _c
for _c in range(ord("a"), ord("z") + 1):
    keyboardMapping[chr(_c)] = ord(chr(_c).upper())
    keyboardMapping[chr(_c).upper()] = 0x0100 + ord(chr(_c).upper())

_OEM_CHAR_MAP = {
    "`": 0xC0,
    "~": 0x01C0,
    "!": 0x0131,
    "@": 0x0132,
    "#": 0x0133,
    "$": 0x0134,
    "%": 0x0135,
    "^": 0x0136,
    "&": 0x0137,
    "*": 0x0138,
    "(": 0x0139,
    ")": 0x0130,
    "-": 0xBD,
    "_": 0x01BD,
    "=": 0xBB,
    "+": 0x01BB,
    "[": 0xDB,
    "{": 0x01DB,
    "]": 0xDD,
    "}": 0x01DD,
    "\\": 0xDC,
    "|": 0x01DC,
    ";": 0xBA,
    ":": 0x01BA,
    "'": 0xDE,
    '"': 0x01DE,
    ",": 0xBC,
    "<": 0x01BC,
    ".": 0xBE,
    ">": 0x01BE,
    "/": 0xBF,
    "?": 0x01BF,
}
keyboardMapping.update(_OEM_CHAR_MAP)


def _resolve_vk(key):
    """Return the (mods, vkCode) for a key, querying Windows VkKeyScanW for unmapped single characters."""
    val = keyboardMapping.get(key)
    if val is None and isinstance(key, str) and len(key) == 1:
        res = int(_bridge.request("VKSCAN %d" % ord(key)))
        if res != -1:
            keyboardMapping[key] = res
            val = res
    if val is None:
        return None
    return divmod(val, 0x100)


def _keyDown(key):
    resolved = _resolve_vk(key)
    if resolved is None:
        return
    mods, vkCode = resolved
    needsShift = pyautogui.isShiftCharacter(key)

    for apply_mod, vk_mod in [(mods & 4, 0x12), (mods & 2, 0x11), (mods & 1 or needsShift, 0x10)]:
        if apply_mod:
            _bridge.request("KEY %d %d" % (vk_mod, KEYEVENTF_KEYDOWN))
    _bridge.request("KEY %d %d" % (vkCode, KEYEVENTF_KEYDOWN))
    for apply_mod, vk_mod in [(mods & 1 or needsShift, 0x10), (mods & 2, 0x11), (mods & 4, 0x12)]:
        if apply_mod:
            _bridge.request("KEY %d %d" % (vk_mod, KEYEVENTF_KEYUP))


def _keyUp(key):
    resolved = _resolve_vk(key)
    if resolved is None:
        return
    mods, vkCode = resolved
    needsShift = pyautogui.isShiftCharacter(key)

    for apply_mod, vk_mod in [(mods & 4, 0x12), (mods & 2, 0x11), (mods & 1 or needsShift, 0x10)]:
        if apply_mod:
            _bridge.request("KEY %d %d" % (vk_mod, KEYEVENTF_KEYDOWN))
    _bridge.request("KEY %d %d" % (vkCode, KEYEVENTF_KEYUP))
    for apply_mod, vk_mod in [(mods & 1 or needsShift, 0x10), (mods & 2, 0x11), (mods & 4, 0x12)]:
        if apply_mod:
            _bridge.request("KEY %d %d" % (vk_mod, KEYEVENTF_KEYUP))


def _position():
    resp = _bridge.request("POS")
    x_str, y_str = resp.split()
    return (int(x_str), int(y_str))


def _size():
    resp = _bridge.request("SIZE")
    w_str, h_str = resp.split()
    return (int(w_str), int(h_str))


def _moveTo(x, y):
    _bridge.request("MOVE %d %d" % (int(x), int(y)))


def _sendMouseEvent(ev, x, y, dwData=0):
    assert x is not None and y is not None, "x and y cannot be set to None"
    _bridge.request("MOUSE %d %d %d %d" % (int(ev), int(x), int(y), int(dwData)))


def _mouseDown(x, y, button):
    if button not in (LEFT, MIDDLE, RIGHT):
        raise ValueError('button arg to _mouseDown() must be one of "left", "middle", or "right", not %s' % button)
    if button == LEFT:
        EV = MOUSEEVENTF_LEFTDOWN
    elif button == MIDDLE:
        EV = MOUSEEVENTF_MIDDLEDOWN
    elif button == RIGHT:
        EV = MOUSEEVENTF_RIGHTDOWN
    _sendMouseEvent(EV, x, y)


def _mouseUp(x, y, button):
    if button not in (LEFT, MIDDLE, RIGHT):
        raise ValueError('button arg to _mouseUp() must be one of "left", "middle", or "right", not %s' % button)
    if button == LEFT:
        EV = MOUSEEVENTF_LEFTUP
    elif button == MIDDLE:
        EV = MOUSEEVENTF_MIDDLEUP
    elif button == RIGHT:
        EV = MOUSEEVENTF_RIGHTUP
    _sendMouseEvent(EV, x, y)


def _click(x, y, button):
    if button not in (LEFT, MIDDLE, RIGHT):
        raise ValueError('button arg to _click() must be one of "left", "middle", or "right", not %s' % button)
    if button == LEFT:
        EV = MOUSEEVENTF_LEFTCLICK
    elif button == MIDDLE:
        EV = MOUSEEVENTF_MIDDLECLICK
    elif button == RIGHT:
        EV = MOUSEEVENTF_RIGHTCLICK
    _sendMouseEvent(EV, x, y)


def _mouse_is_swapped():
    return int(_bridge.request("SWAP")) != 0


def _scroll(clicks, x=None, y=None):
    startx, starty = _position()
    width, height = _size()

    if x is None:
        x = startx
    else:
        x = max(0, min(int(x), width - 1))
    if y is None:
        y = starty
    else:
        y = max(0, min(int(y), height - 1))

    _sendMouseEvent(MOUSEEVENTF_WHEEL, x, y, dwData=int(clicks))


def _hscroll(clicks, x=None, y=None):
    startx, starty = _position()
    width, height = _size()

    if x is None:
        x = startx
    else:
        x = max(0, min(int(x), width - 1))
    if y is None:
        y = starty
    else:
        y = max(0, min(int(y), height - 1))

    _sendMouseEvent(MOUSEEVENTF_HWHEEL, x, y, dwData=int(clicks))


def _vscroll(clicks, x=None, y=None):
    return _scroll(clicks, x, y)


def _wsl_to_win_path(path):
    """Convert a WSL Linux path to a Windows path that powershell.exe can write to."""
    abs_path = os.path.abspath(path)
    wslpath_exe = shutil.which("wslpath")
    if wslpath_exe:
        try:
            proc = subprocess.Popen(
                [wslpath_exe, "-w", abs_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
            out, _ = proc.communicate()
            if proc.returncode == 0 and out.strip():
                return out.strip()
        except Exception:
            pass
    if abs_path.startswith("/mnt/") and len(abs_path) > 6 and abs_path[6] == "/":
        drive = abs_path[5].upper()
        rest = abs_path[6:].replace("/", "\\")
        return "%s:%s" % (drive, rest)
    return abs_path


def _screenshot(imageFilename=None, region=None):
    """Capture a screenshot of the Windows host desktop from WSL."""
    try:
        from PIL import Image
    except ImportError:
        raise pyautogui.PyAutoGUIException(
            "Pillow must be installed to use screenshot functions under WSL."
        )

    if region is not None:
        assert len(region) == 4, "region argument must be a tuple of four ints"
        x, y, width, height = [int(v) for v in region]
    else:
        x, y = 0, 0
        width, height = _size()

    # Use a shared /mnt/c temp directory if available so Windows PowerShell can write directly without UNC issues
    temp_dir = "/mnt/c/Windows/Temp" if os.path.isdir("/mnt/c/Windows/Temp") and os.access("/mnt/c/Windows/Temp", os.W_OK) else None
    fd, tmp_linux_path = tempfile.mkstemp(suffix=".png", dir=temp_dir)
    os.close(fd)
    try:
        win_path = _wsl_to_win_path(tmp_linux_path)
        b64_path = base64.b64encode(win_path.encode("utf-8")).decode("ascii")
        _bridge.request("SCREENSHOT %d %d %d %d %s" % (x, y, width, height, b64_path))
        im = Image.open(tmp_linux_path)
        im.load()
        if imageFilename is not None:
            im.save(imageFilename)
        return im
    finally:
        if os.path.exists(tmp_linux_path):
            try:
                os.unlink(tmp_linux_path)
            except OSError:
                pass

