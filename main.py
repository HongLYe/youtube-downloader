# ===========================================================================
# YouTube Audio Downloader — Backend
# ===========================================================================
# Imports
# ===========================================================================
import glob
import json
import os
import queue
import re
import sys
import threading
from datetime import datetime

import requests
import webview
import yt_dlp


# ===========================================================================
# Cookie setup — fallback chain
# ===========================================================================
import pathlib

def _get_cookie_file_path():
    """Get cookie file path relative to script location."""
    script_dir = pathlib.Path(__file__).parent
    return script_dir / "www.youtube.com_cookies.txt"


KNOWN_COOKIE_FILES = [str(_get_cookie_file_path())]


def _setup_cookies(ydl_opts: dict):
    """Try cookie file first, then Chrome → Firefox → Edge."""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")

    # 1) Cookie file (relative to script, not hardcoded absolute path)
    for cf in KNOWN_COOKIE_FILES:
        if cf and os.path.exists(cf) and os.path.getsize(cf) > 0:
            ydl_opts["cookiefile"] = cf
            return

    # 2) Chrome (Profile/Network/Cookies on modern Chrome)
    for cp in [
        os.path.join(localappdata, r"Google\Chrome\User Data\Default\Network\Cookies"),
        os.path.join(localappdata, r"Google\Chrome\User Data\Profile 1\Network\Cookies"),
        os.path.join(localappdata, r"Google\Chrome\User Data\Profile 2\Network\Cookies"),
    ]:
        if os.path.exists(cp):
            ydl_opts["cookiesfrombrowser"] = ("chrome",)
            return

    # 3) Firefox
    if glob.glob(os.path.join(appdata, r"Mozilla\Firefox\Profiles\*\cookies.sqlite")):
        ydl_opts["cookiesfrombrowser"] = ("firefox",)
        return

    # 4) Edge
    for ep in [
        os.path.join(localappdata, r"Microsoft\Edge\User Data\Default\Network\Cookies"),
        os.path.join(localappdata, r"Microsoft\Edge\User Data\Profile 1\Network\Cookies"),
    ]:
        if os.path.exists(ep):
            ydl_opts["cookiesfrombrowser"] = ("edge",)
            return


# ===========================================================================
# Core Downloader
# ===========================================================================
class YouTubeAudioDownloader:

    # ---------- Lifetime ---------------------------------------------------
    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        self.cover_dir = os.path.join(output_dir, "covers")
        self.song_dir = os.path.join(output_dir, "songs")
        self.history_file = os.path.join(os.path.dirname(__file__), "download_history.json")

        os.makedirs(self.cover_dir, exist_ok=True)
        os.makedirs(self.song_dir, exist_ok=True)

        self.settings = self.load_settings()
        self.download_history = self.load_download_history()
        self.current_window = None
        self.progress_queue = queue.Queue()

    # ---------- Settings ---------------------------------------------------
    def load_settings(self):
        settings_file = os.path.join(os.path.dirname(__file__), "settings.json")
        defaults = {
            "auto_start": True,
            "download_cover": True,
            "add_metadata": True,
            "high_quality": False,
            "organize_files": True,
            "download_folder": self.song_dir,
            "total_downloads": 0,
            "storage_used": "0 MB",
            "last_download": "Never",
        }
        try:
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    defaults.update(loaded)
        except Exception as e:
            print(f"Error loading settings: {e}")
        return defaults

    def save_settings(self, settings):
        for key, value in settings.items():
            self.settings[key] = value
        try:
            with open(os.path.join(os.path.dirname(__file__), "settings.json"),
                      "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    # ---------- Download History -------------------------------------------
    def load_download_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading download history: {e}")
        return []

    def save_download_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.download_history, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving download history: {e}")
            return False

    def add_to_history(self, download_data):
        if "timestamp" not in download_data:
            download_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.download_history.insert(0, download_data)
        if len(self.download_history) > 100:
            self.download_history = self.download_history[:100]
        return self.save_download_history()

    def clear_download_history(self):
        self.download_history = []
        return self.save_download_history()

    def get_download_history(self):
        return self.download_history

    # ---------- Stats ------------------------------------------------------
    def get_download_stats(self):
        return {
            "total_downloads": len(self.download_history),
            "storage_used": self.calculate_storage_used(),
            "last_download": self.get_last_download_time(),
        }

    def calculate_storage_used(self):
        try:
            total = 0
            for root, _, files in os.walk(self.output_dir):
                for f in files:
                    total += os.path.getsize(os.path.join(root, f))
            for unit in ["B", "KB", "MB", "GB"]:
                if total < 1024.0:
                    return f"{total:.1f} {unit}"
                total /= 1024.0
            return f"{total:.1f} GB"
        except Exception:
            return "0 MB"

    def get_last_download_time(self):
        if self.download_history:
            return self.download_history[0].get("timestamp", "Unknown")
        return "Never"

    # ---------- URL Validation ---------------------------------------------
    def is_valid_youtube_url(self, url):
        pattern = (
            r'(https?://)?(www\.)?'
            r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )
        return re.match(pattern, url) is not None

    # ---------- Fetch Video Info -------------------------------------------
    def get_video_info(self, url):
        ydl_opts = {"quiet": True, "no_warnings": True}
        _setup_cookies(ydl_opts)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            duration = info.get("duration", 0) or 0
            minutes, seconds = divmod(duration, 60)
            hours, minutes = divmod(minutes, 60)
            duration_str = (f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0
                            else f"{minutes}:{seconds:02d}") if duration else "Unknown"

            upload_date = info.get("upload_date", "")
            if upload_date:
                try:
                    upload_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
                except Exception:
                    pass

            description = info.get("description", "")
            if description:
                description = description[:200] + "..."

            return {
                "success": True,
                "data": {
                    "title": info.get("title", "Unknown Title"),
                    "author": info.get("uploader", "Unknown Author"),
                    "duration": duration_str,
                    "upload_date": upload_date,
                    "description": description,
                    "thumbnail": info.get("thumbnail", ""),
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("like_count", 0),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- Cover Art --------------------------------------------------
    def download_cover_image(self, url, video_title):
        ydl_opts = {"quiet": True, "no_warnings": True}
        _setup_cookies(ydl_opts)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            thumbnail_url = info.get("thumbnail", "")
            if thumbnail_url:
                clean_title = re.sub(r'[<>:"/\|?*]', '_', video_title)[:150]
                cover_filename = os.path.join(self.cover_dir, f"{clean_title}.jpg")
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                with open(cover_filename, "wb") as f:
                    f.write(response.content)
                return True
            return False
        except Exception as e:
            print(f"⚠️ Could not download cover: {e}")
            return False

    # ---------- Core Download ----------------------------------------------
    def download_audio(self, url, format="m4a", options=None):
        if not self.is_valid_youtube_url(url):
            return {"success": False, "error": "Invalid YouTube URL"}

        options = options or {}
        
        try:
            video_info = self.get_video_info(url)
            if not video_info["success"]:
                return video_info

            video_title = video_info["data"]["title"]

            # Sanitize title for filesystem
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)[:200]

            if options.get("cover", True):
                self.download_cover_image(url, safe_title)

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(self.song_dir, "%(id)s.%(ext)s"),
                "writethumbnail": False,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": format,
                        "preferredquality": "256" if options.get("high_quality", False) else "192",
                    },
                    {"key": "FFmpegMetadata"},
                ],
                "noprogress": False,
                "progress_with_newline": True,
                "progress_hooks": [self.progress_hook_ui],
                "quiet": True,
                "no_warnings": True,
            }
            _setup_cookies(ydl_opts)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)

            actual_file = self.find_downloaded_file(video_title, format)

            download_data = {
                "title": video_title,
                "format": format,
                "duration": video_info["data"]["duration"],
                "size": self.get_actual_file_size(actual_file) if actual_file else "Unknown",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file_path": actual_file if actual_file else f"{safe_title}.{format}",
                "thumbnail": video_info["data"]["thumbnail"],
                "url": url,
            }
            self.add_to_history(download_data)

            return {"success": True, "data": download_data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- Progress Hook ----------------------------------------------
    def progress_hook_ui(self, d):
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes", 0)
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)

            percent = (downloaded / total * 100) if total and total > 0 else 0

            if speed < 1024:
                speed_str = f"{speed:.0f} B/s"
            elif speed < 1024 * 1024:
                speed_str = f"{speed / 1024:.1f} KB/s"
            else:
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s"

            if downloaded < 1024 * 1024:
                downloaded_str = f"{downloaded / 1024:.1f} KB"
            else:
                downloaded_str = f"{downloaded / (1024 * 1024):.1f} MB"

            if total < 1024 * 1024:
                total_str = f"{total / 1024:.1f} KB"
            else:
                total_str = f"{total / (1024 * 1024):.1f} MB"

            eta_str = f"{int(eta // 60):02d}:{int(eta % 60):02d}" if eta else "--:--"

            details = f"Speed: {speed_str} | Downloaded: {downloaded_str} / {total_str} | ETA: {eta_str}"
            self.progress_queue.put(("progress", percent, f"Downloading... {percent:.1f}%", details))

        elif d["status"] == "finished":
            self.progress_queue.put(("progress", 100, "Processing audio...", "Converting format..."))

    # ---------- Queued progress to JS --------------------------------------
    def process_progress_queue(self):
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if self.current_window and msg[0] == "progress":
                    percent, status, details = msg[1], msg[2], msg[3]
                    try:
                        self.current_window.evaluate_js(
                            f"""
                            if (typeof updateProgress === 'function') {{
                                updateProgress({percent}, "{status}", "{details}");
                            }}
                            """
                        )
                    except Exception as e:
                        print(f"Error evaluating JS: {e}")
                self.progress_queue.task_done()
        except queue.Empty:
            pass

    # ---------- File Utilities ---------------------------------------------
    def find_downloaded_file(self, video_title, format):
        try:
            clean_title = re.sub(r'[<>:"/\|?*]', '_', video_title)[:150]
            for filename in os.listdir(self.song_dir):
                if filename.endswith(f".{format}"):
                    if clean_title in filename or video_title in filename:
                        return os.path.join(self.song_dir, filename)
            return None
        except Exception:
            return None

    def get_actual_file_size(self, file_path):
        try:
            if file_path and os.path.exists(file_path):
                size = os.path.getsize(file_path)
                for unit in ["B", "KB", "MB", "GB"]:
                    if size < 1024.0:
                        return f"{size:.1f} {unit}"
                    size /= 1024.0
                return f"{size:.1f} GB"
            return "Unknown size"
        except Exception:
            return "Unknown size"


# ===========================================================================
# PyWebView API Bridge
# ===========================================================================
class Api:
    def __init__(self, downloader):
        self.downloader = downloader
        self.window = None
        self.progress_thread = None

    def set_window(self, window):
        self.downloader.current_window = window
        self.window = window
        self.start_progress_processing()

    # ---------- Download thread --------------------------------------------
    def download_audio(self, url, format, options):
        def download_thread():
            try:
                if self.window:
                    try:
                        self.window.evaluate_js(
                            "if (typeof updateProgress === 'function') {"
                            "updateProgress(0, 'Starting download...', 'Speed: 0 KB/s | Downloaded: 0 KB / 0 KB | ETA: --:--');"
                            "}"
                        )
                    except Exception:
                        pass

                video_info = self.downloader.get_video_info(url)
                if not video_info["success"]:
                    self._js(f"showError('Failed to get video info: {video_info['error']}')")
                    return

                if options.get("cover", True):
                    self.downloader.download_cover_image(url, video_info["data"]["title"])
                    self._js("if (typeof updateProgress === 'function') {"
                             "updateProgress(25, 'Cover downloaded', 'Processing audio...');"
                             "}")

                result = self.downloader.download_audio(url, format, options)

                if result["success"]:
                    data = json.dumps(result["data"])
                    self._js(
                        f"if (typeof showSuccess === 'function') {{ showSuccess('Download completed successfully!'); }}"
                        f"if (typeof updateDownloadStats === 'function') {{ updateDownloadStats(); }}"
                        f"if (typeof addToHistory === 'function') {{ addToHistory({data}); }}"
                        f"if (typeof updateProgress === 'function') {{"
                        f"updateProgress(100, 'Download completed!', 'Speed: 0 KB/s | Downloaded: Complete | ETA: 00:00');"
                        f"}}"
                    )
                else:
                    self._js(
                        f"if (typeof showError === 'function') {{ showError('Download failed: {result['error']}'); }}"
                        f"if (typeof updateProgress === 'function') {{"
                        f"updateProgress(0, 'Download failed', 'Speed: 0 KB/s | Downloaded: 0 KB / 0 KB | ETA: --:--');"
                        f"}}"
                    )
            except Exception as e:
                self._js(f"if (typeof showError === 'function') {{ showError('Download error: {str(e)}'); }}")

        threading.Thread(target=download_thread, daemon=True).start()
        return {"success": True, "message": "Download started..."}

    # ---------- Progress thread --------------------------------------------
    def start_progress_processing(self):
        def tick():
            import time
            while True:
                try:
                    self.downloader.process_progress_queue()
                except Exception as e:
                    print(f"Error in progress processing: {e}")
                time.sleep(0.1)

        if not self.progress_thread or not self.progress_thread.is_alive():
            self.progress_thread = threading.Thread(target=tick, daemon=True)
            self.progress_thread.start()

    # ---------- JS helpers -------------------------------------------------
    def _js(self, code):
        """Send JS to the webview, silently ignoring errors."""
        if self.window:
            try:
                self.window.evaluate_js(code)
            except Exception:
                pass

    # ---------- Delegated downloads ----------------------------------------
    def get_video_info(self, url):
        return self.downloader.get_video_info(url)

    def get_download_stats(self):
        return self.downloader.get_download_stats()

    def get_download_history(self):
        return self.downloader.get_download_history()

    def clear_download_history(self):
        return {"success": self.downloader.clear_download_history()}

    def get_settings(self):
        return self.downloader.settings

    def save_settings(self, settings):
        return {"success": self.downloader.save_settings(settings)}

    # ---------- File-system operations -------------------------------------
    @staticmethod
    def _open(path, reveal=False):
        if sys.platform == "win32":
            if reveal:
                import subprocess
                subprocess.Popen(f'explorer /select,"{path}"')
            else:
                os.startfile(path)
        elif sys.platform == "darwin":
            import subprocess
            cmd = ["open", "-R", path] if reveal else ["open", path]
            subprocess.Popen(cmd)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", os.path.dirname(path) if reveal else path])
        return {"success": True}

    def open_download_folder(self):
        try:
            return self._open(self.downloader.song_dir)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def change_download_folder(self):
        try:
            result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            if result:
                folder_path = result[0]
                self.downloader.song_dir = folder_path
                self.downloader.settings["download_folder"] = folder_path
                self.downloader.save_settings({})
                return {"success": True, "folder": folder_path}
            return {"success": False, "error": "No folder selected"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def play_audio(self, file_path):
        try:
            return self._open(file_path)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def show_in_folder(self, file_path):
        try:
            return self._open(file_path, reveal=True)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- Window management ------------------------------------------
    def close_app(self):
        """Close the application window."""
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
        return {"success": True}

    def minimize_app(self):
        """Minimize the application window."""
        if self.window:
            try:
                self.window.minimize()
            except Exception:
                pass
        return {"success": True}

    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.window:
            try:
                self.window.toggle_fullscreen()
            except Exception:
                pass
        return {"success": True}


# ===========================================================================
# Entry point
# ===========================================================================
def main():
    downloader = YouTubeAudioDownloader()
    api = Api(downloader)

    window = webview.create_window(
        "YouTube Audio Downloader",
        "ui/index.html",
        width=1200,
        height=700,
        resizable=True,
        min_size=(900, 600),
        text_select=False,
        confirm_close=False,
        background_color="#1a1a2e",
        frameless=True,
        draggable=True,
    )

    api.set_window(window)

    window.expose(
        api.get_video_info,
        api.download_audio,
        api.get_download_stats,
        api.get_download_history,
        api.clear_download_history,
        api.get_settings,
        api.save_settings,
        api.open_download_folder,
        api.change_download_folder,
        api.play_audio,
        api.show_in_folder,
        api.close_app,
        api.minimize_app,
        api.toggle_fullscreen,
    )

    webview.start(debug=False, http_server=False, private_mode=False)


if __name__ == "__main__":
    main()
