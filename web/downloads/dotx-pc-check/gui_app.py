from __future__ import annotations

import json
import os
import sys
import ctypes
import threading
import traceback
import urllib.error
import urllib.request
from pathlib import Path

import tkinter as tk
from tkinter import font as tkfont

from pccheck.models import Severity
from pccheck.report.text_report import build_text
from cleanup import schedule_self_delete

PIN_LENGTH = 6
WIN_W = 640
WIN_H = 360

BLUE_BG = "#3d96d4"
WHITE = "#ffffff"
WHITE_SOFT = "#d8ecff"
WHITE_DIM = "#9ecae8"
LOGO_WHITE = "#f2f7ff"
LOGO_RED = "#8b1a28"
LOGO_SHADOW = "#1a5080"
SUCCESS = "#b8ffd8"
ERROR = "#ffb4b4"
PIN_BOX_BG = "#6eb0e0"
PIN_BORDER = "#d6ebff"
PIN_BORDER_FOCUS = "#ffffff"
CORNER_RADIUS = 20
PIN_BOX_W = 36
PIN_BOX_H = 42
PIN_BOX_GAP = 8

GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040


def _window_hwnd(window: tk.Misc) -> int:
    hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
    return hwnd or window.winfo_id()


def ensure_taskbar_presence(window: tk.Misc) -> None:
    """Keep frameless windows in the taskbar and Alt+Tab switcher on Windows."""
    if sys.platform != "win32":
        return
    window.update_idletasks()
    hwnd = _window_hwnd(window)
    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(
        hwnd,
        GWL_EXSTYLE,
        (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW,
    )
    ctypes.windll.user32.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW,
    )


def apply_rounded_frameless(window: tk.Tk, radius: int = CORNER_RADIUS) -> None:
    if sys.platform != "win32":
        window.overrideredirect(True)
        return
    window.overrideredirect(True)
    window.update_idletasks()
    ensure_taskbar_presence(window)
    hwnd = _window_hwnd(window)
    width = window.winfo_width()
    height = window.winfo_height()
    rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
    ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def assets_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "assets"
        if bundled.exists():
            return bundled
    nested = app_dir() / "assets"
    return nested if nested.exists() else app_dir()


DOTX_CONFIG_MARKER = b"DOTXCONFIG"


def load_embedded_server_url() -> str | None:
    if not getattr(sys, "frozen", False):
        return None
    data = Path(sys.executable).read_bytes()
    idx = data.rfind(DOTX_CONFIG_MARKER)
    if idx == -1:
        return None
    try:
        payload = data[idx + len(DOTX_CONFIG_MARKER) :].decode("utf-8")
        config = json.loads(payload)
        url = str(config.get("serverUrl", "")).strip().rstrip("/")
        return url or None
    except (UnicodeDecodeError, json.JSONDecodeError, OSError):
        return None


def load_server_url() -> str:
    embedded = load_embedded_server_url()
    if embedded:
        return embedded

    config_path = app_dir() / "dotx.config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            url = str(data.get("serverUrl", "")).strip().rstrip("/")
            if url:
                return url
        except (json.JSONDecodeError, OSError):
            pass
    return "http://127.0.0.1:8080"


def find_asset(name: str) -> Path | None:
    for folder in (assets_dir(), app_dir()):
        path = folder / name
        if path.exists():
            return path
    return None


def count_severities(result) -> tuple[int, int]:
    threats = 0
    warnings = 0
    for finding in result.findings:
        if finding.severity in (Severity.CRITICAL, Severity.HIGH):
            threats += 1
        elif finding.severity in (Severity.MEDIUM, Severity.LOW):
            warnings += 1
    return threats, warnings


def upload_scan(server_url: str, pin: str, result, report_text: str) -> tuple[bool, str]:
    threats, warnings = count_severities(result)
    payload = {
        "pin": pin,
        "verdict": result.verdict,
        "threats": threats,
        "warnings": warnings,
        "summary": f"{result.verdict} — {len(result.findings)} findings",
        "reportText": report_text,
        "hostname": result.hostname,
        "username": result.username,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{server_url}/api/scans/submit",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "dotx-pc-check/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return True, "Report sent to dotx panel."
            return False, data.get("error") or "Upload failed."
    except urllib.error.HTTPError as err:
        try:
            data = json.loads(err.read().decode("utf-8"))
            message = data.get("error") or err.reason
        except (json.JSONDecodeError, OSError):
            message = err.reason
        if err.code == 404:
            return False, "Invalid PIN. Ask staff for a new PIN from the dotx panel."
        return False, f"Upload failed ({message})."
    except urllib.error.URLError:
        return False, "Could not reach dotx server. Check your internet and try again."
    except Exception as err:
        return False, str(err)


class CanvasPinInput:
    def __init__(self, canvas: tk.Canvas, cx: int, cy: int, on_complete) -> None:
        self.canvas = canvas
        self.cx = cx
        self.cy = cy
        self.on_complete = on_complete
        self.digits = [""] * PIN_LENGTH
        self.focus_index = 0
        self.rect_ids: list[int] = []
        self.char_ids: list[int] = []
        self.digit_font = tkfont.Font(family="Segoe UI", size=17, weight="bold")
        self._alive = True
        self._completed = False
        self._draw()

        self._key_bind = canvas.bind("<Key>", self._on_key, add="+")
        self._click_bind = canvas.bind("<Button-1>", self._on_click, add="+")
        canvas.focus_set()

    def _box_origin(self) -> tuple[int, int]:
        total_w = PIN_LENGTH * PIN_BOX_W + (PIN_LENGTH - 1) * PIN_BOX_GAP
        return self.cx - total_w // 2, self.cy - PIN_BOX_H // 2

    def _index_at(self, x: int, _y: int) -> int | None:
        start_x, _ = self._box_origin()
        for i in range(PIN_LENGTH):
            x1 = start_x + i * (PIN_BOX_W + PIN_BOX_GAP)
            if x1 <= x <= x1 + PIN_BOX_W:
                return i
        return None

    def _draw(self) -> None:
        if not self._alive:
            return
        for rid in self.rect_ids:
            self.canvas.delete(rid)
        for cid in self.char_ids:
            self.canvas.delete(cid)
        self.rect_ids.clear()
        self.char_ids.clear()

        start_x, start_y = self._box_origin()
        for i in range(PIN_LENGTH):
            x1 = start_x + i * (PIN_BOX_W + PIN_BOX_GAP)
            y1 = start_y
            x2 = x1 + PIN_BOX_W
            y2 = y1 + PIN_BOX_H
            focused = i == self.focus_index
            rid = self.canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=PIN_BORDER_FOCUS if focused else PIN_BORDER,
                width=3 if focused else 2,
                fill="",
            )
            self.rect_ids.append(rid)
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
            char = self.digits[i]
            if char:
                cid = self.canvas.create_text(cx, cy, text=char, fill=WHITE, font=self.digit_font)
                self.char_ids.append(cid)
            elif focused:
                cid = self.canvas.create_text(cx, cy, text="|", fill=WHITE, font=self.digit_font, tags="pin_cursor")
                self.char_ids.append(cid)

    def _on_click(self, event) -> None:
        if not self._alive:
            return
        idx = self._index_at(event.x, event.y)
        if idx is not None:
            self.focus_index = idx
            self._draw()
            self.canvas.focus_set()

    def _on_key(self, event) -> str | None:
        if not self._alive or self._completed:
            return "break"
        if event.keysym == "BackSpace":
            if self.digits[self.focus_index]:
                self.digits[self.focus_index] = ""
            elif self.focus_index > 0:
                self.focus_index -= 1
                self.digits[self.focus_index] = ""
            self._draw()
            return "break"

        if event.char and event.char.isdigit():
            self.digits[self.focus_index] = event.char
            if self.focus_index < PIN_LENGTH - 1:
                self.focus_index += 1
            self._draw()
            if all(self.digits):
                self._completed = True
                self.on_complete("".join(self.digits))
            return "break"
        if event.char:
            return "break"
        return None

    def focus(self) -> None:
        self.canvas.focus_set()
        self._draw()

    def destroy(self) -> None:
        self._alive = False
        self._completed = True
        try:
            self.canvas.unbind("<Key>", self._key_bind)
            self.canvas.unbind("<Button-1>", self._click_bind)
        except tk.TclError:
            pass
        for rid in self.rect_ids:
            self.canvas.delete(rid)
        for cid in self.char_ids:
            self.canvas.delete(cid)
        self.canvas.delete("pin_cursor")
        self.rect_ids.clear()
        self.char_ids.clear()


class DotxApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.server_url = load_server_url()
        self.pin_input: CanvasPinInput | None = None
        self.scan_thread: threading.Thread | None = None
        self._images: list[tk.PhotoImage] = []
        self._using_bg_image = False
        self._drag_offset: tuple[int, int] | None = None
        self._scan_anim_token = 0
        self._screen = "pin"
        self._session_finished = False

        self.title("dotx PC Check")
        self.configure(bg=BLUE_BG)
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)

        self.logo_dot_font = tkfont.Font(family="Segoe UI", size=62, weight="bold")
        self.logo_x_font = tkfont.Font(family="Segoe UI", size=62, weight="bold")
        self.label_font = tkfont.Font(family="Segoe UI", size=10)
        self.status_font = tkfont.Font(family="Segoe UI", size=11)
        self.small_font = tkfont.Font(family="Segoe UI", size=9)
        self.spinner_font = tkfont.Font(family="Segoe UI", size=20, weight="bold")

        self.canvas = tk.Canvas(
            self, width=WIN_W, height=WIN_H, highlightthickness=0, bd=0, bg=BLUE_BG, takefocus=1
        )
        self.canvas.pack(fill="both", expand=True)
        self._bg_photo: tk.PhotoImage | None = None
        self._bind_window_drag()
        self.bind("<FocusIn>", self._on_window_focus)
        self.bind("<Map>", self._on_window_focus)
        self._apply_window_icon()

        self.show_pin_screen()
        self.after(80, self._apply_window_style)

    def _on_window_focus(self, _event=None) -> None:
        if not self.winfo_exists():
            return
        self.lift()
        self.attributes("-topmost", True)
        self.after(50, lambda: self.attributes("-topmost", False) if self.winfo_exists() else None)

    def finish_session(self, delay_ms: int = 2500) -> None:
        if self._session_finished:
            return
        self._session_finished = True
        self.after(delay_ms, self._exit_and_cleanup)

    def _exit_and_cleanup(self) -> None:
        schedule_self_delete()
        try:
            self.quit()
            self.destroy()
        except tk.TclError:
            pass
        os._exit(0)

    def _content_bg(self) -> str:
        return BLUE_BG

    def _apply_window_style(self) -> None:
        apply_rounded_frameless(self, CORNER_RADIUS)
        ensure_taskbar_presence(self)

    def _bind_window_drag(self) -> None:
        self.canvas.bind("<ButtonPress-1>", self._start_drag, add="+")
        self.canvas.bind("<B1-Motion>", self._on_drag, add="+")
        self.canvas.bind("<ButtonRelease-1>", self._end_drag, add="+")

    def _start_drag(self, event) -> None:
        item = self.canvas.find_closest(event.x, event.y)
        if item and "close_btn" in self.canvas.gettags(item[0]):
            return
        if self.pin_input and self.pin_input._index_at(event.x, event.y) is not None:
            return
        self._drag_offset = (event.x, event.y)

    def _on_drag(self, event) -> None:
        if not self._drag_offset:
            return
        dx, dy = self._drag_offset
        self.geometry(f"+{self.winfo_x() + event.x - dx}+{self.winfo_y() + event.y - dy}")

    def _end_drag(self, _event) -> None:
        self._drag_offset = None

    def _remember_image(self, image: tk.PhotoImage) -> tk.PhotoImage:
        self._images.append(image)
        return image

    def _load_photo(self, filename: str) -> tk.PhotoImage | None:
        path = find_asset(filename)
        if not path:
            return None
        try:
            return self._remember_image(tk.PhotoImage(file=str(path)))
        except tk.TclError:
            return None

    def clear_screen(self) -> None:
        self._scan_anim_token += 1
        if self.pin_input:
            self.pin_input.destroy()
            self.pin_input = None
        for widget in self.canvas.winfo_children():
            widget.destroy()
        self.canvas.delete("all")
        for attr in (
            "scan_spinner_id",
            "scan_status_id",
            "progress_bg_id",
            "progress_fg_id",
            "pin_error_id",
        ):
            if hasattr(self, attr):
                delattr(self, attr)

    def _fit_photo(self, image: tk.PhotoImage, target_w: int, target_h: int) -> tk.PhotoImage:
        w, h = image.width(), image.height()
        if w <= target_w and h <= target_h:
            return image
        factor = 1
        while w // factor > target_w or h // factor > target_h:
            factor += 1
        return image.subsample(factor, factor)

    def _draw_backdrop(self) -> int:
        bg = self._load_photo("background.png") or self._load_photo("dotx-bg.png")
        if bg:
            self._using_bg_image = True
            self._bg_photo = self._fit_photo(bg, WIN_W, WIN_H)
            self.canvas.config(width=WIN_W, height=WIN_H)
            self.geometry(f"{WIN_W}x{WIN_H}")
            self.canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")
            self.after(10, self._apply_window_style)
            return WIN_H

        self._using_bg_image = False
        self.canvas.config(width=WIN_W, height=WIN_H)
        self.geometry(f"{WIN_W}x{WIN_H}")
        for i in range(WIN_W):
            t = i / max(WIN_W - 1, 1)
            r = int(45 + (95 - 45) * t)
            g = int(120 + (185 - 120) * t)
            b = int(200 + (240 - 200) * t)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_line(i, 0, i, WIN_H, fill=color)
        self.after(10, self._apply_window_style)
        return WIN_H

    def _place_close_button(self) -> None:
        w = self.canvas.winfo_reqwidth() or WIN_W
        close = self.canvas.create_text(
            w - 22,
            18,
            text="✕",
            fill=WHITE_SOFT,
            font=tkfont.Font(family="Segoe UI", size=12),
            tags="close_btn",
        )
        self.canvas.tag_bind(close, "<Button-1>", lambda _e: self.destroy())
        self.canvas.tag_bind(close, "<Enter>", lambda _e: self.canvas.itemconfig(close, fill=WHITE))
        self.canvas.tag_bind(close, "<Leave>", lambda _e: self.canvas.itemconfig(close, fill=WHITE_SOFT))

    def _apply_window_icon(self) -> None:
        ico = find_asset("dotx.ico")
        if ico and sys.platform == "win32":
            try:
                self.iconbitmap(str(ico))
            except tk.TclError:
                pass
        logo = self._load_photo("logo.png")
        if logo:
            try:
                self.iconphoto(True, logo)
            except tk.TclError:
                pass

    def _logo_photo(self, max_size: int = 140) -> tk.PhotoImage | None:
        logo = self._load_photo("logo.png")
        if not logo:
            return None
        return self._fit_photo(logo, max_size, max_size)

    def _draw_logo(self, cx: int, cy: int) -> None:
        logo = self._logo_photo(140)
        if logo:
            self.canvas.create_image(cx, cy, image=logo, anchor="center")
            return

        dot_x = cx - 54
        x_x = cx + 50

        self.canvas.create_text(dot_x + 2, cy + 2, text="Dot", font=self.logo_dot_font, fill=LOGO_SHADOW)
        self.canvas.create_text(x_x + 2, cy + 2, text="X", font=self.logo_x_font, fill="#5a1020")
        self.canvas.create_text(dot_x, cy, text="Dot", font=self.logo_dot_font, fill=LOGO_WHITE)
        self.canvas.create_text(x_x, cy, text="X", font=self.logo_x_font, fill=LOGO_RED)

    def _bg_zones(self, height: int) -> dict[str, int]:
        return {
            "label": int(height * 0.58),
            "content": int(height * 0.68),
            "sub": int(height * 0.76),
            "bar": int(height * 0.84),
            "hint": int(height * 0.90),
        }

    def show_pin_screen(self) -> None:
        self._screen = "pin"
        self.clear_screen()
        height = self._draw_backdrop()
        cx = (self.canvas.winfo_reqwidth() or WIN_W) // 2

        if self._using_bg_image:
            zones = self._bg_zones(height)
            label_y = zones["label"]
            boxes_y = zones["content"]
            line_y = zones["bar"]
            hint_y = zones["hint"]
        else:
            logo_y = int(height * 0.34)
            label_y = int(height * 0.56)
            boxes_y = int(height * 0.66)
            line_y = int(height * 0.76)
            hint_y = int(height * 0.86)

        self._place_close_button()
        if not self._using_bg_image:
            self._draw_logo(cx, logo_y)

        self.canvas.create_text(cx, label_y, text="Enter PIN Code", fill=WHITE_SOFT, font=self.label_font)

        self.pin_input = CanvasPinInput(self.canvas, cx, boxes_y, self._on_pin_complete)
        self.canvas.create_line(cx - 150, line_y, cx + 150, line_y, fill=WHITE_DIM)
        self.canvas.create_text(
            cx,
            hint_y,
            text=f"{PIN_LENGTH} digits · 0-9",
            fill=WHITE_SOFT,
            font=self.small_font,
        )
        self.pin_error_id = self.canvas.create_text(cx, hint_y + 18, text="", fill=ERROR, font=self.small_font)

        self.after(50, self.pin_input.focus)

    def _on_pin_complete(self, pin: str) -> None:
        if self._screen != "pin":
            return
        if self.pin_input:
            self.pin_input.destroy()
            self.pin_input = None
        self.after(140, lambda p=pin: self.start_scan(p))

    def start_scan(self, pin: str) -> None:
        if self._screen != "pin":
            return
        if self.scan_thread and self.scan_thread.is_alive():
            return
        self.show_scan_screen(pin)
        self.scan_thread = threading.Thread(target=self.run_scan, args=(pin,), daemon=True)
        self.scan_thread.start()

    def show_scan_screen(self, pin: str) -> None:
        self._screen = "scan"
        self._scan_pin = pin
        self.clear_screen()
        height = self._draw_backdrop()
        cx = (self.canvas.winfo_reqwidth() or WIN_W) // 2

        self._place_close_button()
        if self._using_bg_image:
            zones = self._bg_zones(height)
            title_y = zones["label"]
            spinner_y = zones["content"]
            status_y = zones["sub"]
            bar_y = zones["bar"]
            pin_y = zones["hint"]
        else:
            logo_y = int(height * 0.30)
            self._draw_logo(cx, logo_y)
            title_y = int(height * 0.50)
            spinner_y = int(height * 0.60)
            status_y = int(height * 0.72)
            bar_y = int(height * 0.84)
            pin_y = int(height * 0.92)

        self.canvas.create_text(cx, title_y, text="Scanning your PC", fill=WHITE, font=self.label_font)

        self.scan_spinner_id = self.canvas.create_text(
            cx,
            spinner_y,
            text="...",
            fill=WHITE,
            font=self.spinner_font,
        )

        self.scan_status_id = self.canvas.create_text(
            cx, status_y, text="Starting modules...", fill=WHITE_SOFT, font=self.status_font
        )

        self.canvas.create_text(cx, pin_y, text=f"PIN {pin}", fill=WHITE_DIM, font=self.small_font)

        bar_x1 = cx - 120
        bar_x2 = cx + 120
        self.progress_bg_id = self.canvas.create_line(bar_x1, bar_y, bar_x2, bar_y, fill=WHITE_DIM, width=3)
        self.progress_fg_id = self.canvas.create_line(bar_x1, bar_y, bar_x1, bar_y, fill=WHITE, width=3)

        self._spinner_frames = ["   ", ".  ", ".. ", "..."]
        self._spinner_index = 0
        self._progress_value = 0
        token = self._scan_anim_token
        self._animate_scan(token)

    def _animate_scan(self, token: int) -> None:
        if token != self._scan_anim_token or self._screen != "scan":
            return
        if not hasattr(self, "scan_spinner_id") or not self.canvas.winfo_exists():
            return
        try:
            self.canvas.coords(self.scan_spinner_id)
        except tk.TclError:
            return
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        self.canvas.itemconfig(self.scan_spinner_id, text=self._spinner_frames[self._spinner_index])
        if self._progress_value < 92:
            self._progress_value += 2
            bar_x1 = (self.canvas.winfo_reqwidth() or WIN_W) // 2 - 120
            bar_y_coords = self.canvas.coords(self.progress_bg_id)
            if len(bar_y_coords) >= 2:
                bar_y = bar_y_coords[1]
                end_x = bar_x1 + int(240 * self._progress_value / 100)
                self.canvas.coords(self.progress_fg_id, bar_x1, bar_y, end_x, bar_y)
        self.after(180, lambda: self._animate_scan(token))

    def set_scan_status(self, text: str) -> None:
        if self._screen != "scan":
            return
        if hasattr(self, "scan_status_id") and self.canvas.winfo_exists():
            try:
                self.canvas.itemconfig(self.scan_status_id, text=text)
            except tk.TclError:
                pass

    def run_scan(self, pin: str) -> None:
        try:
            import os
            import socket
            import time

            from pccheck.models import ScanResult
            from pccheck.scanners import (
                BrowserScanner,
                CleanerScanner,
                FileScanner,
                FiveMScanner,
                PEScanner,
                PrefetchScanner,
                ProcessScanner,
                RegistryScanner,
                RpfScanner,
            )

            scanners = [
                ProcessScanner(),
                PrefetchScanner(),
                RegistryScanner(),
                PEScanner(),
                RpfScanner(),
                FileScanner(),
                FiveMScanner(),
                BrowserScanner(),
                CleanerScanner(),
            ]

            result = ScanResult(
                hostname=socket.gethostname(),
                username=os.environ.get("USERNAME", "unknown"),
            )
            start = time.perf_counter()

            for idx, scanner in enumerate(scanners, start=1):
                label = scanner.name
                self.after(
                    0,
                    lambda l=label, i=idx, t=len(scanners): self.set_scan_status(f"Running {l} ({i}/{t})..."),
                )
                result.modules_run.append(scanner.name)
                try:
                    scanner.scan(result)
                except Exception as exc:
                    result.errors.append(f"{scanner.name} failed: {exc}")

            result.scan_duration_sec = time.perf_counter() - start

            report_text = build_text(result)
            report_text = f"dotx PIN: {pin}\r\n\r\n{report_text}"

            self.after(0, lambda: self.set_scan_status("Uploading report to dotx..."))
            ok, message = upload_scan(self.server_url, pin, result, report_text)
            self.after(0, lambda: self.show_done_screen(pin, result, ok, message))
        except Exception:
            err = traceback.format_exc()
            self.after(0, lambda: self.show_error_screen(err))

    def show_done_screen(self, pin: str, result, uploaded: bool, message: str) -> None:
        self._screen = "done"
        self.clear_screen()
        height = self._draw_backdrop()
        cx = (self.canvas.winfo_reqwidth() or WIN_W) // 2
        color = SUCCESS if uploaded else ERROR
        icon = "✓" if uploaded else "!"

        self._place_close_button()
        if self._using_bg_image:
            zones = self._bg_zones(height)
            icon_y = zones["content"]
            title_y = zones["sub"]
            detail_y = zones["bar"]
            message_y = zones["hint"]
        else:
            logo_y = int(height * 0.28)
            self._draw_logo(cx, logo_y)
            icon_y = int(height * 0.48)
            title_y = int(height * 0.62)
            detail_y = int(height * 0.70)
            message_y = int(height * 0.80)

        self.canvas.create_text(
            cx,
            icon_y,
            text=icon,
            fill=color,
            font=tkfont.Font(family="Segoe UI", size=40, weight="bold"),
        )

        title = "Scan complete" if uploaded else "Scan finished"
        closing_note = "Closing and removing tool..."
        full_message = f"{message}\n\n{closing_note}" if message else closing_note
        self.canvas.create_text(cx, title_y, text=title, fill=WHITE, font=self.label_font)
        self.canvas.create_text(
            cx, detail_y, text=f"PIN {pin} · {result.verdict}", fill=WHITE_SOFT, font=self.small_font
        )
        self.canvas.create_text(
            cx,
            message_y,
            text=full_message,
            fill=color,
            font=self.status_font,
            width=360,
            justify="center",
        )
        self.finish_session(2500 if uploaded else 4000)

    def show_error_screen(self, err: str) -> None:
        self._screen = "error"
        self.clear_screen()
        height = self._draw_backdrop()
        cx = (self.canvas.winfo_reqwidth() or WIN_W) // 2

        self._place_close_button()
        if self._using_bg_image:
            zones = self._bg_zones(height)
            title_y = zones["label"]
            err_y = zones["content"]
        else:
            self._draw_logo(cx, int(height * 0.28))
            title_y = int(height * 0.48)
            err_y = int(height * 0.62)
        self.canvas.create_text(cx, title_y, text="Scan failed", fill=ERROR, font=self.label_font)
        self.canvas.create_text(
            cx,
            err_y,
            text=f"{err[:380]}\n\nClosing and removing tool...",
            fill=WHITE_SOFT,
            font=self.small_font,
            width=360,
            justify="left",
        )
        self.finish_session(5000)


def main() -> None:
    app = DotxApp()
    app.mainloop()


if __name__ == "__main__":
    main()
