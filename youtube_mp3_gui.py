#!/usr/bin/env python3
"""YouTube MP3 Downloader — minimal GUI."""

import glob
import os
import re
import shutil
import threading
from datetime import datetime
from pathlib import Path

import urllib.parse

import customtkinter as ctk
import yt_dlp

try:
    import pywinstyles
except ImportError:
    pywinstyles = None

# ---------------------------------------------------------------------------
# Detect system dark mode
# ---------------------------------------------------------------------------
try:
    import winreg
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
    ) as key:
        dark_mode = winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
except Exception:
    dark_mode = True

ctk.set_appearance_mode("dark" if dark_mode else "light")
ctk.set_default_color_theme("blue")

# ---------------------------------------------------------------------------
# Theme palette — muted, macOS-inspired
# ---------------------------------------------------------------------------
if dark_mode:
    BG = "#1e1e1e"
    SURFACE = "#2c2c2e"
    ACCENT = "#007aff"
    ACCENT_HOVER = "#005ecb"
    TEXT_PRIMARY = "#f5f5f7"
    TEXT_SECONDARY = "#8e8e93"
    BORDER = "#3a3a3c"
    SUCCESS = "#30d158"
    ERROR = "#ff453a"
    PROGRESS_BG = "#3a3a3c"
    FONT = "Segoe UI Variable"
else:
    BG = "#f5f5f7"
    SURFACE = "#ffffff"
    ACCENT = "#007aff"
    ACCENT_HOVER = "#005ecb"
    TEXT_PRIMARY = "#1d1d1f"
    TEXT_SECONDARY = "#86868b"
    BORDER = "#d2d2d7"
    SUCCESS = "#34c759"
    ERROR = "#ff3b30"
    PROGRESS_BG = "#e5e5ea"
    FONT = "Segoe UI Variable"

OUTPUT_DIR = r"C:\Users\GioZ\Desktop\Music_mp3"
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

WATERMARK = "256 kbps  ·  MP3"
QUALITY_BITRATE = "256"

# Cookie file path (lives next to the script)
COOKIE_FILE = Path(__file__).parent / "www.youtube.com_cookies.txt"

# Sentinel for clean thread cancellation
_CANCEL_MARKER = object()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
YT_URL_RE = re.compile(
    r"(https?://)?(www\.|m\.)?((youtube\.com/((watch\?v=)|(playlist\?list=))"
    r"|(youtu\.be/)|(music\.youtube\.com/)).+)",
    re.IGNORECASE,
)


def is_yt_url(s: str) -> bool:
    return bool(YT_URL_RE.match(s))


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# Cookie helper — file first, then browser fallback
# ---------------------------------------------------------------------------
def _setup_cookies(ydl_opts: dict):
    """Use cookie file if present and non-empty, else fall back to browser.

    Note: Chrome stores cookies in Profile/N\\Cookies on Windows 10+.
    The Cookies file is locked while the browser is running —
    yt-dlp handles this by making a shadow copy, but it only
    works when called as --cookies-from-browser chrome.
    """
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")

    # Check if cookie file exists AND has content
    if COOKIE_FILE.is_file() and COOKIE_FILE.stat().st_size > 0:
        ydl_opts["cookiefile"] = str(COOKIE_FILE)
        return

    # Fall back to browser cookies: chrome > firefox > edge
    # Chrome stores cookies in Profile/Network/Cookies (modern Chrome)
    chrome_profile_dirs = [
        os.path.join(localappdata,
                     r"Google\Chrome\User Data\Default\Network\Cookies"),
        os.path.join(localappdata,
                     r"Google\Chrome\User Data\Profile 1\Network\Cookies"),
        os.path.join(localappdata,
                     r"Google\Chrome\User Data\Profile 2\Network\Cookies"),
    ]
    for cp in chrome_profile_dirs:
        if os.path.exists(cp):
            ydl_opts["cookiesfrombrowser"] = ("chrome",)
            return

    # Firefox
    ff_profiles = glob.glob(os.path.join(appdata,
                                         r"Mozilla\Firefox\Profiles\*\cookies.sqlite"))
    if ff_profiles:
        ydl_opts["cookiesfrombrowser"] = ("firefox",)
        return

    # Edge (same subdirectory structure as Chrome)
    edge_profile_dirs = [
        os.path.join(localappdata,
                     r"Microsoft\Edge\User Data\Default\Network\Cookies"),
        os.path.join(localappdata,
                     r"Microsoft\Edge\User Data\Profile 1\Network\Cookies"),
    ]
    for ep in edge_profile_dirs:
        if os.path.exists(ep):
            ydl_opts["cookiesfrombrowser"] = ("edge",)
            return


# ---------------------------------------------------------------------------
# Download worker
# ---------------------------------------------------------------------------
def download_worker(url, output_dir, queue: dict, cancel_event: threading.Event):
    def progress_hook(d):
        if cancel_event.is_set():
            raise yt_dlp.utils.DownloadError("Download cancelled by user")

        if d["status"] == "downloading":
            pct_str = d.get("_percent_str", "?")
            speed_str = d.get("_speed_str", "N/A")
            eta_str = d.get("_eta_str", "")
            queue["status"] = f"Downloading {pct_str}  \u2022  {speed_str}"
            if eta_str:
                queue["status"] += f"  \u2022  ETA: {eta_str}"
            # Robust percentage parsing
            try:
                raw = pct_str.replace("%", "").replace("~", "").replace(",", ".").strip()
                pct = float(raw)
                queue["progress"] = max(0.0, min(0.91, pct / 100.0))
            except (ValueError, TypeError, AttributeError):
                pass
        elif d["status"] == "finished":
            queue["status"] = "Converting to MP3\u2026"
            queue["progress"] = 0.92

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(Path(output_dir) / "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": QUALITY_BITRATE,
            }
        ],
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "android", "web_music"],
                "player_skip": ["configs"],
            }
        },
        "sleep_interval": 1,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "retry_sleep": {"extractor": 3},
    }

    _setup_cookies(ydl_opts)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        if cancel_event.is_set():
            queue["status"] = "Cancelled"
            queue["done"] = True
            queue["success"] = False
            return

        entries = info.get("entries") or []
        if entries:
            count = len([e for e in entries if e])
            queue["status"] = f"{count} tracks saved"
        else:
            title = info.get("title", "Unknown")
            queue["status"] = title

        queue["progress"] = 1.0
        queue["done"] = True
        queue["success"] = True

    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc)
        if cancel_event.is_set() or "cancelled" in msg.lower():
            queue["status"] = "Cancelled"
        elif "unavailable" in msg.lower() or "private" in msg.lower():
            queue["status"] = "Video unavailable"
        elif "bot" in msg.lower() or "sign in" in msg.lower() or "login" in msg.lower():
            queue["status"] = "YouTube bot detection — refresh cookies.txt"
        elif "timed out" in msg or "connection" in msg.lower():
            queue["status"] = "Network error"
        elif "not available in your country" in msg.lower():
            queue["status"] = "Not available in your region"
        else:
            queue["status"] = msg[:120]
        queue["done"] = True
        queue["success"] = False
    except Exception as exc:
        msg = str(exc)
        if cancel_event.is_set():
            queue["status"] = "Cancelled"
        else:
            queue["status"] = msg[:120]
        queue["done"] = True
        queue["success"] = False


# ---------------------------------------------------------------------------
# Progress bar drawing
# ---------------------------------------------------------------------------
RADIUS = 3


def _draw_progress_bar(canvas: ctk.CTkCanvas, value: float, width: int):
    h = 6
    canvas.delete("all")
    r = RADIUS
    canvas.create_polygon(
        _rounded_coords(0, 0, width, h, r),
        smooth=True, fill=PROGRESS_BG, outline="",
    )
    if value > 0:
        fill_w = max(2 * r, int(width * value))
        canvas.create_polygon(
            _rounded_coords(0, 0, fill_w, h, r),
            smooth=True, fill=ACCENT, outline="",
        )


def _rounded_coords(x1, y1, x2, y2, r):
    return [
        x1 + r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------
class App(ctk.CTk):
    WIDTH = 440
    HEIGHT = 380

    def __init__(self):
        super().__init__()
        self.title("YouTube MP3")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(380, 320)
        self.resizable(True, True)

        # Frosted glass effect (may fail gracefully)
        try:
            if pywinstyles is not None:
                pywinstyles.apply_style(self, "acrylic" if dark_mode else "mica")
        except Exception:
            pass
        self.attributes("-alpha", 0.95)

        # On close, cancel any active download cleanly
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ---------- Header ----------
        header = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Music Downloader",
            font=ctk.CTkFont(family=FONT, size=28, weight="normal"),
            text_color=TEXT_PRIMARY, anchor="w",
        ).grid(row=0, column=0, padx=28, pady=(28, 2), sticky="w")

        ctk.CTkLabel(
            header, text=WATERMARK,
            font=ctk.CTkFont(family=FONT, size=13, weight="normal"),
            text_color=TEXT_SECONDARY, anchor="w",
        ).grid(row=1, column=0, padx=28, pady=(0, 12), sticky="w")

        # ---------- URL card ----------
        url_card = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=16)
        url_card.grid(row=1, column=0, padx=28, pady=20, sticky="ew")
        url_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            url_card, text="URL",
            font=ctk.CTkFont(family=FONT, size=11),
            text_color=TEXT_SECONDARY, anchor="w",
        ).grid(row=0, column=0, padx=(20, 20), pady=(18, 0), sticky="w")

        self.url_var = ctk.StringVar()
        self.url_entry = ctk.CTkEntry(
            url_card, textvariable=self.url_var,
            placeholder_text="youtube.com/watch?v=\u2026",
            font=ctk.CTkFont(family=FONT, size=15),
            height=44, corner_radius=12, border_width=1,
            border_color=BORDER, fg_color=SURFACE, text_color=TEXT_PRIMARY,
        )
        self.url_entry.grid(row=1, column=0, padx=20, pady=(8, 18), sticky="ew")
        self.url_entry.bind("<Return>", lambda e: self._start_download())

        # ---------- Download / Cancel button ----------
        btn_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        btn_frame.grid(row=2, column=0, padx=28, pady=(0, 8), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        self.dl_btn = ctk.CTkButton(
            btn_frame, text="Download",
            font=ctk.CTkFont(family=FONT, size=16, weight="normal"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#ffffff", height=52, corner_radius=14,
            command=self._start_download, cursor="hand2",
        )
        self.dl_btn.grid(row=0, column=0, padx=0, pady=(0, 8), sticky="ew")

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel",
            font=ctk.CTkFont(family=FONT, size=16, weight="normal"),
            fg_color=ERROR, hover_color="#d63228",
            text_color="#ffffff", height=52, corner_radius=14,
            command=self._cancel_download, cursor="hand2",
        )

        # ---------- Progress + status ----------
        bottom_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        bottom_frame.grid(row=3, column=0, padx=28, pady=(0, 20), sticky="nsew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkCanvas(
            bottom_frame, height=6, bg=BG,
            highlightthickness=0, bd=0,
        )
        self.progress_bar.pack(fill="x", pady=(8, 8))
        self._progress_value = 0.0

        self.after(100, self._render_progress)

        self.status_label = ctk.CTkLabel(
            bottom_frame, text="Ready",
            font=ctk.CTkFont(family=FONT, size=13),
            text_color=TEXT_SECONDARY, anchor="w",
        )
        self.status_label.pack(fill="x", pady=(0, 8))

        self._downloading = False
        self._cancel_event = threading.Event()
        self._poll_active = False  # guards after() on destroyed window

        # ffmpeg check (non-fatal — will show warning)
        if not shutil.which("ffmpeg"):
            self.status_label.configure(text="ffmpeg not found on PATH", text_color=ERROR)

    # ------------------------------------------------------------------
    # URL validation
    # ------------------------------------------------------------------
    def _validate_url(self, url: str):
        if not url.strip():
            self.status_label.configure(text="Please enter a URL", text_color=ERROR)
            return False
        if not is_yt_url(url):
            self.status_label.configure(
                text="Invalid YouTube URL", text_color=ERROR)
            return False
        return True

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def _start_download(self):
        if self._downloading:
            return

        url = self.url_var.get().strip()
        if not self._validate_url(url):
            return

        self._downloading = True
        self._cancel_event.clear()
        self._poll_active = True

        # Swap buttons
        self.dl_btn.grid_remove()
        self.cancel_btn.grid(row=0, column=0, padx=0, pady=(0, 8), sticky="ew")

        self._set_progress(0)
        self.status_label.configure(text="Starting\u2026", text_color=TEXT_SECONDARY)

        queue = {"status": "", "progress": 0.0, "done": False, "success": False}

        thread = threading.Thread(
            target=download_worker,
            args=(url, OUTPUT_DIR, queue, self._cancel_event),
            daemon=True,
        )
        thread.start()
        self._poll_queue(queue)

    def _cancel_download(self):
        if not self._downloading:
            return
        self._cancel_event.set()
        self.status_label.configure(text="Cancelling\u2026", text_color=TEXT_SECONDARY)

    def _on_close(self):
        self._cancel_event.set()
        self._poll_active = False
        self.destroy()

    def _set_progress(self, value):
        self._progress_value = max(0.0, min(1.0, value))
        self._render_progress()

    def _render_progress(self):
        if not self._poll_active:
            return
        try:
            w = self.progress_bar.winfo_width()
            if w <= 0:
                w = 380
            _draw_progress_bar(self.progress_bar, self._progress_value, w)
        except Exception:
            pass

    def _poll_queue(self, queue: dict):
        if not self._poll_active:
            return
        try:
            if queue["status"]:
                self.status_label.configure(text=queue["status"])
            self._set_progress(queue["progress"])

            if queue["done"]:
                self._downloading = False
                # Swap buttons back
                self.cancel_btn.grid_remove()
                self.dl_btn.grid(row=0, column=0, padx=0, pady=(0, 8), sticky="ew")
                c = SUCCESS if queue["success"] else ERROR
                self.status_label.configure(text_color=c)
                if queue["success"]:
                    self._set_progress(1.0)
            else:
                self.after(150, self._poll_queue, queue)
        except ctk.CTkTclError:
            # Widget destroyed during poll — stop silently
            self._poll_active = False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
