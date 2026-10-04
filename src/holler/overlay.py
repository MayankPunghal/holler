"""The status pill: a small, modern, click-through overlay that shows what the dictation tool is doing.

    listening     red dot + live waveform that follows your voice (flat grey if the mic is dead)
    transcribing  blue dot + a flowing wave
    done          a green check, then it fades away
    messages      dot + one short line ("Learned", "Didn't catch that", ...)

How it is drawn (Windows): the pill is rendered with Pillow at 2x and scaled down, so edges and the soft
shadow are properly anti-aliased, then pushed to a layered window with per-pixel alpha
(UpdateLayeredWindow). The window never takes focus and ignores the mouse, so your paste always goes
to the app you were using. It only wakes up while visible, and idles at ~10 checks per second otherwise.
Elsewhere (or if that fails) a plain Tk pill is used.

    python overlay.py --preview docs      # write preview images of every state
    python overlay.py --demo              # play the states live in a real window (needs Tk)
"""
import math
import os
import queue
import sys
import threading
import time
import traceback

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 2  # supersampling factor for drawing

BG = (24, 24, 27)
RED, BLUE, GREEN, AMBER, GREY = (255, 69, 58), (100, 170, 255), (48, 209, 88), (255, 189, 46), (142, 142, 147)
VIOLET = (190, 160, 255)

# state: (kind, accent colour, label, seconds until it hides itself)
STATES = {
    "loading":      ("text",  AMBER, "Loading model",              None),
    "ready":        ("text",  GREEN, "Ready \u00b7 hold {key}",    2.2),
    "listening":    ("wave",  RED,   None,                         None),
    "transcribing": ("think", BLUE,  None,                         None),
    "done":         ("check", GREEN, None,                         0.55),
    "empty":        ("text",  GREY,  "Didn't catch that",          1.4),
    "nomic":        ("text",  AMBER, "No audio \u00b7 check your mic", 2.5),
    "cancelled":    ("text",  GREY,  "Cancelled",                  0.9),
    "error":        ("text",  RED,   "Something went wrong \u00b7 see errors.log", 3.5),
    "learned":      ("text",  GREEN, "Learned",                    1.6),
    "nothing":      ("text",  GREY,  "Nothing new to learn",       1.6),
    "undone":       ("text",  GREY,  "Removed the last dictation", 1.4),
    "noundo":       ("text",  GREY,  "Nothing to undo here",       1.6),
    "nomatch":      ("text",  GREY,  "Select the corrected sentence first", 2.4),
}


# --------------------------------------------------------------------------- drawing

def _load_font(px: float):
    px = max(8, int(round(px)))
    for name in (r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\segoeui.ttf",
                 "/System/Library/Fonts/SFNS.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "DejaVuSans-Bold.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


_KEY_NAMES = {"ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "win": "Win", "ctrl_r": "Right Ctrl",
              "ctrl_l": "Left Ctrl", "alt_gr": "AltGr", "space": "Space"}


def key_label(spec: str) -> str:
    """'ctrl+shift' -> 'Ctrl+Shift', 'f9' -> 'F9'."""
    return "+".join(_KEY_NAMES.get(p, p.upper() if len(p) <= 3 else p.capitalize()) for p in spec.split("+"))


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class PillRenderer:
    """Pure drawing + animation state (no OS calls), so it can be tested and previewed anywhere."""

    W, H, PILL_H = 360, 84, 36            # logical canvas / pill size in px at 100% scaling
    N_BARS = 15
    ENV = tuple(math.exp(-((i - 7) / 4.2) ** 2) * 0.85 + 0.15 for i in range(15))   # centre-weighted bars

    def __init__(self, scale: float = 1.0, key_name: str = "key"):
        self.s = float(scale)
        self.key = key_name
        self.font = _load_font(12.5 * self.s * SS)
        self.small = _load_font(11 * self.s * SS)
        self.bar_h = [3.0] * self.N_BARS
        self.state = None
        self.kind, self.accent, self.label = "text", GREY, ""
        self.width = self.target_w = 112.0
        self.alpha, self.want = 0.0, False
        self.level_raw = self.level = 0.0
        self.quiet = 0.0
        self.t = self.state_t = 0.0
        self.hide_after = None

    @property
    def size(self):
        return int(self.W * self.s), int(self.H * self.s)

    # ---- state
    def set(self, state: str, level: float = 0.0):
        if state == "hide":
            self.want = False
            return
        if state == "listening" and self.state == "listening" and self.want:
            self.level_raw = level                      # just a meter update
            return
        kind, accent, label, auto = STATES[state]
        self.state, self.kind, self.accent = state, kind, accent
        self.label = (label or "").format(key=key_label(self.key))
        self.state_t, self.hide_after, self.want = 0.0, auto, True
        self.level_raw = level if state == "listening" else 0.0
        self.quiet = 0.0
        self.target_w = self._target_width()
        if self.alpha < 0.03:
            self.width = self.target_w                  # appear at full size, don't grow from nothing

    def _target_width(self):
        if self.kind == "wave":
            return 168.0                                 # dot, waveform, timer
        if self.kind == "think":
            return 128.0
        if self.kind == "check":
            return 52.0
        return max(110.0, 34 + self.font.getlength(self.label) / (SS * self.s) + 18)

    def step(self, dt: float) -> bool:
        """Advance animations by dt seconds. Returns True while the pill is visible."""
        self.t += dt
        self.state_t += dt
        if self.want and self.hide_after is not None and self.state_t >= self.hide_after:
            self.want = False
        if self.want:
            self.alpha = min(1.0, self.alpha + dt / 0.12)
        else:
            self.alpha = max(0.0, self.alpha - dt / 0.25)
        self.width += (self.target_w - self.width) * (1 - math.exp(-dt * 16))
        target = min(1.0, (self.level_raw / 0.10) ** 0.55) if self.kind == "wave" else 0.0
        k = 1 - math.exp(-dt * (30 if target > self.level else 7))   # fast attack, slow release
        self.level += (target - self.level) * k
        if self.kind == "wave":                                      # bars glide towards the voice level
            dead = self.quiet > 1.2
            for i in range(self.N_BARS):
                jit = 0.62 + 0.38 * (0.5 + 0.5 * math.sin(self.t * 8.5 + i * 1.3) * math.cos(self.t * 3.1 + i * 0.7))
                want = 2.6 if dead else 2.6 + 22.0 * self.level * self.ENV[i] * jit
                self.bar_h[i] += (want - self.bar_h[i]) * (1 - math.exp(-dt * 18))
        if self.kind == "wave" and self.level_raw < 0.004:
            self.quiet += dt
        elif self.kind == "wave":
            self.quiet = 0.0
        return self.alpha > 0.01

    # ---- drawing
    def render(self) -> Image.Image:
        """Return the current frame as straight-alpha RGBA, size = self.size."""
        s = self.s * SS
        W, H = self.W, self.H
        im = Image.new("RGBA", (int(W * s), int(H * s)), (0, 0, 0, 0))
        a = 1 - (1 - self.alpha) ** 3                              # ease-out
        cx, cy = W / 2, H / 2 + (1 - a) * 8                        # slides up as it appears
        w, h = self.width, self.PILL_H * (0.92 + 0.08 * a)
        x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2
        c = lambda col, al=255: (*col, int(al * a))

        # body: a soft vertical gradient (lighter at the top), a hairline border and a top highlight
        body = Image.new("RGBA", im.size, (0, 0, 0, 0))
        grad = Image.new("RGBA", im.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        top, bot = (44, 44, 50), (20, 20, 23)
        for yy in range(int(y0 * s), int(y1 * s) + 1):
            f = (yy - y0 * s) / max(1.0, (y1 - y0) * s)
            gd.line([(0, yy), (im.size[0], yy)], fill=(*_mix(top, bot, f), int(238 * a)))
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=h / 2 * s, fill=255)
        body.paste(grad, (0, 0), mask)
        im = Image.alpha_composite(im, body)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=h / 2 * s, outline=c((255, 255, 255), 30),
                            width=max(1, int(round(s * 0.8))))
        {"wave": self._wave, "think": self._think, "check": self._check, "text": self._text}[self.kind](
            d, s, c, x0, x1, cy)

        out = im.resize(self.size, Image.LANCZOS)
        # soft drop shadow, drawn at 1x (cheap) and composited underneath
        sh = Image.new("L", self.size, 0)
        ImageDraw.Draw(sh).rounded_rectangle(
            [(x0 + 2) * self.s, (y0 + 5) * self.s, (x1 - 2) * self.s, (y1 + 5) * self.s], radius=h / 2 * self.s,
            fill=int(120 * a))
        sh = sh.filter(ImageFilter.GaussianBlur(7 * self.s))
        shadow = Image.new("RGBA", self.size, (0, 0, 0, 0))
        shadow.putalpha(sh)
        return Image.alpha_composite(shadow, out)

    def _dot(self, d, s, c, x, cy, pulse=False, breathe=False):
        col = self.accent
        if pulse:
            ph = (self.t * 1.4) % 1.0                                  # a ring that grows and fades, like a beacon
            r = 4 + 6 * ph
            d.ellipse([(x - r) * s, (cy - r) * s, (x + r) * s, (cy + r) * s], outline=c(col, int(150 * (1 - ph))),
                      width=max(1, int(1.4 * s)))
        al = 150 + 105 * (0.5 + 0.5 * math.sin(self.t * 4)) if breathe else 255
        r = 5.2
        d.ellipse([(x - r) * s, (cy - r) * s, (x + r) * s, (cy + r) * s], fill=c(col, int(al * 0.25)))
        r = 3.6
        d.ellipse([(x - r) * s, (cy - r) * s, (x + r) * s, (cy + r) * s], fill=c(col, al))

    def _bars(self, d, s, c, x0, x1, cy, heights, colours, right=18):
        n, bw, gap = self.N_BARS, 2.4, 2.7
        total = n * bw + (n - 1) * gap
        bx = x0 + 32 + ((x1 - right) - (x0 + 32) - total) / 2
        for i in range(n):
            x = bx + i * (bw + gap)
            hh = heights[i]
            d.rounded_rectangle([x * s, (cy - hh / 2) * s, (x + bw) * s, (cy + hh / 2) * s],
                                radius=bw / 2 * s, fill=c(colours[i][:3], colours[i][3] if len(colours[i]) > 3 else 255))

    def _wave(self, d, s, c, x0, x1, cy):
        dead = self.quiet > 1.2
        self._dot(d, s, c, x0 + 20, cy, pulse=not dead)
        cols = [(140, 140, 145, 150) if dead else (*_mix((255, 255, 255), self.accent, abs(i - 7) / 9), 240)
                for i in range(self.N_BARS)]
        self._bars(d, s, c, x0, x1, cy, self.bar_h, cols, right=46)
        secs = int(self.state_t)
        d.text(((x1 - 16) * s, cy * s), f"{secs // 60}:{secs % 60:02d}", font=self.small,
               fill=c((235, 235, 240), 150), anchor="rm")

    def _think(self, d, s, c, x0, x1, cy):
        self._dot(d, s, c, x0 + 20, cy, breathe=True)
        heights = [2.6 + 12.0 * self.ENV[i] * (0.5 + 0.5 * math.sin(self.t * 6 - i * 0.55)) for i in range(self.N_BARS)]
        cols = [(*_mix(BLUE, VIOLET, i / (self.N_BARS - 1)), 240) for i in range(self.N_BARS)]
        self._bars(d, s, c, x0, x1, cy, heights, cols)

    def _check(self, d, s, c, x0, x1, cy):
        p = min(1.0, self.state_t / 0.26)
        pts = [(-6.5, 0.5), (-2.0, 5.0), (6.5, -4.8)]
        mx = (x0 + x1) / 2
        seg = [math.dist(pts[0], pts[1]), math.dist(pts[1], pts[2])]
        run = p * sum(seg)
        path = [pts[0]]
        if run <= seg[0]:
            f = run / seg[0]
            path.append((pts[0][0] + (pts[1][0] - pts[0][0]) * f, pts[0][1] + (pts[1][1] - pts[0][1]) * f))
        else:
            f = (run - seg[0]) / seg[1]
            path += [pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * f, pts[1][1] + (pts[2][1] - pts[1][1]) * f)]
        xy = [((mx + x) * s, (cy + y) * s) for x, y in path]
        g = min(1.0, self.state_t / 0.18)
        r = 11 * g
        d.ellipse([(mx - r) * s, (cy - r) * s, (mx + r) * s, (cy + r) * s], fill=c((30, 70, 42), 255))
        col = c(GREEN)
        d.line(xy, fill=col, width=int(2.8 * s), joint="curve")
        for px, py in (xy[0], xy[-1]):                              # round caps
            r = 1.4 * s
            d.ellipse([px - r, py - r, px + r, py + r], fill=col)

    def _text(self, d, s, c, x0, x1, cy):
        self._dot(d, s, c, x0 + 19, cy, breathe=self.state == "loading")
        d.text(((x0 + 33) * s, cy * s), self.label, font=self.font, fill=c((246, 246, 248), 240), anchor="lm")


def to_bgra_premultiplied(img: Image.Image) -> bytes:
    """What UpdateLayeredWindow wants: B, G, R, A with colour pre-multiplied by alpha."""
    arr = np.asarray(img, dtype=np.uint8)
    a = arr[..., 3:4].astype(np.uint16)
    rgb = (arr[..., :3].astype(np.uint16) * a + 127) // 255
    out = np.empty_like(arr)
    out[..., 0], out[..., 1], out[..., 2], out[..., 3] = rgb[..., 2], rgb[..., 1], rgb[..., 0], arr[..., 3]
    return out.tobytes()


# --------------------------------------------------------------------------- windows

class NullOverlay:
    def set(self, state, level=0.0):
        pass

    def run(self):
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


def _win_dpi():
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor aware: crisp, not bitmap-scaled
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except Exception:
        return 1.0


class LayeredPill:
    """Windows: Tk only provides the window handle and the event loop; pixels come from PillRenderer."""

    GWL_EXSTYLE = -20
    WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT, WS_EX_LAYERED, WS_EX_NOACTIVATE = 0x8, 0x80, 0x20, 0x80000, 0x08000000

    def __init__(self, key_name: str, fps: int = 30):
        import ctypes
        import tkinter as tk
        from ctypes import wintypes as wt

        scale = _win_dpi()
        self.q = queue.Queue()
        self.r = PillRenderer(scale, key_name)
        self.fps = fps
        self.shown = False
        self.top_t = 0.0
        self.last = time.monotonic()

        user32, gdi32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("gdi32", use_last_error=True)
        self.user32, self.gdi32, self.ct, self.wt = user32, gdi32, ctypes, wt
        H, P, I, U, B = wt.HWND, ctypes.c_void_p, ctypes.c_int, wt.UINT, wt.BOOL
        user32.GetDC.argtypes, user32.GetDC.restype = [H], wt.HDC
        user32.ReleaseDC.argtypes, user32.ReleaseDC.restype = [H, wt.HDC], I
        user32.GetAncestor.argtypes, user32.GetAncestor.restype = [H, U], H
        user32.GetWindowLongW.argtypes, user32.GetWindowLongW.restype = [H, I], wt.LONG
        user32.SetWindowLongW.argtypes, user32.SetWindowLongW.restype = [H, I, wt.LONG], wt.LONG
        user32.SetWindowPos.argtypes, user32.SetWindowPos.restype = [H, H, I, I, I, I, U], B
        user32.ShowWindow.argtypes, user32.ShowWindow.restype = [H, I], B
        user32.SystemParametersInfoW.argtypes, user32.SystemParametersInfoW.restype = [U, U, P, U], B
        gdi32.CreateCompatibleDC.argtypes, gdi32.CreateCompatibleDC.restype = [wt.HDC], wt.HDC
        gdi32.SelectObject.argtypes, gdi32.SelectObject.restype = [wt.HDC, wt.HGDIOBJ], wt.HGDIOBJ

        class POINT(ctypes.Structure):
            _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

        class SIZE(ctypes.Structure):
            _fields_ = [("cx", wt.LONG), ("cy", wt.LONG)]

        class BLEND(ctypes.Structure):
            _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

        class BMIH(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                        ("biClrImportant", wt.DWORD)]

        class BMI(ctypes.Structure):
            _fields_ = [("bmiHeader", BMIH), ("bmiColors", wt.DWORD * 3)]

        class RECT(ctypes.Structure):
            _fields_ = [("left", wt.LONG), ("top", wt.LONG), ("right", wt.LONG), ("bottom", wt.LONG)]

        self.POINT, self.SIZE, self.BLEND, self.RECT = POINT, SIZE, BLEND, RECT
        gdi32.CreateDIBSection.argtypes = [wt.HDC, ctypes.POINTER(BMI), U, ctypes.POINTER(P), wt.HANDLE, wt.DWORD]
        gdi32.CreateDIBSection.restype = wt.HBITMAP
        user32.UpdateLayeredWindow.argtypes = [H, wt.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE), wt.HDC,
                                               ctypes.POINTER(POINT), wt.COLORREF, ctypes.POINTER(BLEND), wt.DWORD]
        user32.UpdateLayeredWindow.restype = B

        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry("+0+0")
        self.root.update_idletasks()
        hwnd = user32.GetAncestor(self.root.winfo_id(), 2) or self.root.winfo_id()   # GA_ROOT
        self.hwnd = hwnd
        ex = user32.GetWindowLongW(hwnd, self.GWL_EXSTYLE)
        ex |= self.WS_EX_LAYERED | self.WS_EX_TOOLWINDOW | self.WS_EX_NOACTIVATE | self.WS_EX_TRANSPARENT | self.WS_EX_TOPMOST
        user32.SetWindowLongW(hwnd, self.GWL_EXSTYLE, ex)
        # HWND_TOPMOST = -1; NOMOVE|NOSIZE|NOACTIVATE|FRAMECHANGED
        user32.SetWindowPos(hwnd, wt.HWND(-1), 0, 0, 0, 0, 0x2 | 0x1 | 0x10 | 0x20)

        cw, ch = self.r.size
        self.cw, self.ch = cw, ch
        bmi = BMI()
        bmi.bmiHeader.biSize = ctypes.sizeof(BMIH)
        bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = cw, -ch          # negative = top-down rows
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount, bmi.bmiHeader.biCompression = 1, 32, 0
        self.hdc_screen = user32.GetDC(None)
        self.hdc_mem = gdi32.CreateCompatibleDC(self.hdc_screen)
        self.bits = P()
        self.hbmp = gdi32.CreateDIBSection(self.hdc_screen, ctypes.byref(bmi), 0, ctypes.byref(self.bits), None, 0)
        if not self.hbmp or not self.bits.value:
            raise RuntimeError("CreateDIBSection failed")
        gdi32.SelectObject(self.hdc_mem, self.hbmp)
        self._present(None)                                             # prove the layered path works at init
        user32.ShowWindow(hwnd, 0)

    # ---- public
    def set(self, state, level=0.0):
        self.q.put((state, level))

    def run(self):
        self.last = time.monotonic()
        self.root.after(100, self._tick)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

    # ---- internals
    def _origin(self):
        rc = self.RECT()
        self.user32.SystemParametersInfoW(0x30, 0, self.ct.byref(rc), 0)   # SPI_GETWORKAREA
        x = rc.left + (rc.right - rc.left - self.cw) // 2
        y = rc.bottom - self.ch - int(6 * self.r.s)
        return x, y

    def _present(self, img, origin=(0, 0)):
        if img is not None:
            data = to_bgra_premultiplied(img)
            self.ct.memmove(self.bits.value, data, len(data))
        pt, sz, src = self.POINT(*origin), self.SIZE(self.cw, self.ch), self.POINT(0, 0)
        blend = self.BLEND(0, 0, 255, 1)                                  # AC_SRC_OVER, per-pixel alpha
        ok = self.user32.UpdateLayeredWindow(self.hwnd, self.hdc_screen, self.ct.byref(pt), self.ct.byref(sz),
                                             self.hdc_mem, self.ct.byref(src), 0, self.ct.byref(blend), 2)  # ULW_ALPHA
        if not ok:
            raise OSError(f"UpdateLayeredWindow failed ({self.ct.get_last_error()})")

    def _raise(self):
        """Put the pill at the top of the topmost band without activating it (apps that also call themselves
        topmost, full-screen apps and the taskbar can otherwise end up above it). HWND_TOPMOST = -1;
        NOMOVE | NOSIZE | NOACTIVATE | SHOWWINDOW."""
        self.user32.SetWindowPos(self.hwnd, self.wt.HWND(-1), 0, 0, 0, 0, 0x2 | 0x1 | 0x10 | 0x40)

    def _tick(self):
        now = time.monotonic()
        dt, self.last = min(0.1, now - self.last), now
        try:
            while True:
                self.r.set(*self.q.get_nowait())
        except queue.Empty:
            pass
        visible = self.r.step(dt)
        if visible:
            origin = self._origin()
            try:
                self._present(self.r.render(), origin)
            except Exception:
                _log("overlay frame")
            if not self.shown or now - self.top_t > 0.1:
                self._raise()                                             # show + stay above every other window
                self.shown, self.top_t = True, now
        elif self.shown:
            self.user32.ShowWindow(self.hwnd, 0)
            self.shown = False
        self.root.after(int(1000 / self.fps) if visible else 100, self._tick)


# --------------------------------------------------------------------------- fallback (any OS)

class ClassicOverlay:
    """Plain Tk pill: used on macOS/Linux, or on Windows if the layered window can't be created."""
    W, H = 260, 46

    def __init__(self, key_name: str):
        import tkinter as tk
        self.q = queue.Queue()
        self.key = key_name.upper()
        self.state, self.hide_at = None, None
        self.root = tk.Tk()
        r = self.root
        r.withdraw()
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-alpha", 0.94)
        r.configure(bg="#18181b")
        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        r.geometry(f"{self.W}x{self.H}+{(sw - self.W) // 2}+{sh - self.H - 90}")
        self.c = tk.Canvas(r, width=self.W, height=self.H, bg="#18181b", highlightthickness=0)
        self.c.pack()
        self.dot = self.c.create_oval(14, 15, 30, 31, fill="#ff453a", outline="")
        self.txt = self.c.create_text(42, 23, anchor="w", fill="white", font=("Segoe UI", 11, "bold"), text="")
        self.bar = self.c.create_rectangle(10, 40, 10, 43, fill="#30d158", outline="")
        r.update_idletasks()
        if sys.platform == "win32":
            try:
                import ctypes
                u = ctypes.windll.user32
                hwnd = u.GetParent(r.winfo_id()) or r.winfo_id()
                st = u.GetWindowLongW(hwnd, -20)
                u.SetWindowLongW(hwnd, -20, st | 0x80 | 0x08000000 | 0x20)
            except Exception:
                pass

    def set(self, state, level=0.0):
        self.q.put((state, level))

    def _poll(self):
        changed = False
        try:
            while True:
                state, level = self.q.get_nowait()
                if state == "hide":
                    self.state, self.hide_at = None, None
                    self.root.withdraw()
                    continue
                if state == "listening" and self.state == "listening":
                    self.c.coords(self.bar, 10, 40, 10 + int(min(1.0, level * 14) * (self.W - 20)), 43)
                    continue
                self.state, changed = state, True
        except queue.Empty:
            pass
        if changed and self.state:
            kind, accent, label, auto = STATES[self.state]
            text = label.format(key=self.key) if label else {"listening": "Listening", "transcribing": "Transcribing...",
                                                           "done": "Pasted"}.get(self.state, "")
            self.c.itemconfig(self.dot, fill="#%02x%02x%02x" % accent)
            self.c.itemconfig(self.txt, text=text)
            self.c.coords(self.bar, 10, 40, 10, 43)
            self.hide_at = time.time() + auto if auto else None
            self.root.deiconify()
            self.root.lift()
        if self.state and int(time.time() * 2) != getattr(self, "_top_n", None):
            self._top_n = int(time.time() * 2)
            self.root.attributes("-topmost", True)               # stay above apps that also claim topmost
            self.root.lift()
        if self.hide_at and time.time() >= self.hide_at:
            self.hide_at, self.state = None, None
            self.root.withdraw()
        self.root.after(40, self._poll)

    def run(self):
        self.root.after(40, self._poll)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass


_LOG = {"fn": None}


def _log(where: str):
    if _LOG["fn"]:
        _LOG["fn"](where)
    else:
        traceback.print_exc()


def make_overlay(enabled: bool, key_name: str, ui: str = "auto", log=None):
    """ui: 'auto' (pill on Windows, classic elsewhere), 'pill', 'classic'."""
    _LOG["fn"] = log
    if not enabled:
        return NullOverlay()
    if ui in ("auto", "pill") and sys.platform == "win32":
        try:
            return LayeredPill(key_name)
        except Exception:
            _log("pill overlay unavailable, using classic")
    try:
        return ClassicOverlay(key_name)
    except Exception:
        _log("classic overlay")
        return NullOverlay()


# --------------------------------------------------------------------------- preview / demo

def _speech_level(t):
    """A believable speech envelope for previews: bursts of syllables with small gaps."""
    syl = max(0.0, math.sin(t * 7.3)) ** 1.5 * (0.55 + 0.45 * math.sin(t * 2.1 + 1))
    return 0.015 + 0.16 * syl


def render_sequence(scale=2.0, fps=30):
    """Frames for ready -> listening -> transcribing -> done, on a transparent canvas. Yields (state, Image)."""
    r = PillRenderer(scale, "ctrl_r")
    dt = 1.0 / fps
    plan = [("ready", 1.2), ("listening", 3.0), ("transcribing", 1.3), ("done", 1.1)]
    for state, dur in plan:
        r.set(state, _speech_level(0))
        n = int(dur * fps)
        for i in range(n):
            if state == "listening":
                r.set("listening", _speech_level(i * dt))
            r.step(dt)
            yield state, r.render()
    for _ in range(int(0.4 * fps)):
        r.step(dt)
        yield "end", r.render()


def make_previews(outdir: str):
    os.makedirs(outdir, exist_ok=True)
    scale = 2.0
    states = [("listening", "Listening"), ("transcribing", "Transcribing"), ("done", "Done"),
              ("ready", "Ready"), ("empty", "No speech"), ("learned", "Learned")]
    tiles = []
    for name, caption in states:
        r = PillRenderer(scale, "ctrl_r")
        r.set(name, 0.09)
        for i in range(45 if name in ("listening", "transcribing") else 18):
            if name == "listening":
                r.set("listening", _speech_level(i / 30))
            r.step(1 / 30)
            if name == "done" and r.state_t > 0.4:
                break
        tiles.append((caption, r.render()))
    tw, th = tiles[0][1].size
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    for theme, bg in (("dark", (30, 31, 36)), ("light", (238, 240, 244))):
        sheet = Image.new("RGB", (tw * cols, (th + 20) * rows), bg)
        d = ImageDraw.Draw(sheet)
        font = _load_font(14)
        for i, (caption, tile) in enumerate(tiles):
            x, y = (i % cols) * tw, (i // cols) * (th + 20)
            sheet.paste(tile, (x, y), tile)
            d.text((x + tw // 2, y + th + 4), caption, font=font, fill=(150, 150, 160), anchor="mm")
        sheet.save(os.path.join(outdir, f"pill-states-{theme}.png"))
    # animated GIF of a whole dictation, on a dark desktop-ish background
    frames = []
    bg = (30, 31, 36)
    for state, img in render_sequence(scale=1.5):
        base = Image.new("RGB", img.size, bg)
        base.paste(img, (0, 0), img)
        frames.append(base.quantize(colors=48, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    frames[0].save(os.path.join(outdir, "pill-demo.gif"), save_all=True, append_images=frames[1:],
                   duration=int(1000 / 30), loop=0, optimize=True, disposal=2)
    print("wrote previews to", outdir)


def demo():
    ov = make_overlay(True, "ctrl+shift", "auto", log=None)
    print("Indicator in use:", type(ov).__name__, "(LayeredPill = the modern pill)", flush=True)

    def feed():
        time.sleep(0.5)
        for state, dur in (("ready", 1.8), ("listening", 3.5), ("transcribing", 1.5), ("done", 1.5),
                           ("empty", 1.6), ("learned", 1.6), ("error", 2.0)):
            ov.set(state, 0.0)
            t0 = time.time()
            while time.time() - t0 < dur:
                if state == "listening":
                    ov.set("listening", _speech_level(time.time() - t0))
                time.sleep(0.05)
        os._exit(0)
    threading.Thread(target=feed, daemon=True).start()
    ov.run()


if __name__ == "__main__":
    if "--preview" in sys.argv:
        i = sys.argv.index("--preview")
        make_previews(sys.argv[i + 1] if len(sys.argv) > i + 1 else "docs")
    elif "--demo" in sys.argv:
        demo()
    else:
        print(__doc__)
