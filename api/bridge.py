"""API bridge for PyWebView - handles threading and JS communication."""
import json
import sys
import threading

import webview

from core import YouTubeAudioDownloader
from core.validators import clean_url
from utils.platform import open_file as _open_platform


class Api:
    """Bridge between the core downloader and the UI layer."""

    def __init__(self, downloader=None):
        self.downloader = downloader or YouTubeAudioDownloader()
        self.window = None
        self.progress_thread = None

    def set_window(self, window):
        self.window = window
        self.start_progress_processing()

    def download_audio(self, url, format, options):
        url = clean_url(url)
        options = options or {}

        def download_thread():
            try:
                print(f"[download] Starting: {url}")
                self._js(
                    "if (typeof updateProgress === 'function') { "
                    "updateProgress(0, 'Starting download...', "
                    "'Speed: 0 KB/s | Downloaded: 0 KB / 0 KB | ETA: --:--'); "
                    "} "
                )

                result = self.downloader.download_audio(url, format, options)

                if result["success"]:
                    message = result.get("message", "Download completed successfully!")
                    self._js(
                        "if (typeof onDownloadComplete === 'function') { "
                        f"onDownloadComplete({json.dumps(message)}, {json.dumps(result['data'])}); "
                        "} "
                    )
                else:
                    self._js(
                        "if (typeof onDownloadFailed === 'function') { "
                        f"onDownloadFailed({json.dumps('Download failed: ' + result['error'])}); "
                        "} "
                    )
            except Exception as e:
                print(f"[download] Error: {e}")
                self._js(
                    "if (typeof onDownloadFailed === 'function') { "
                    f"onDownloadFailed({json.dumps('Download error: ' + str(e))}); "
                    "} "
                )

        threading.Thread(target=download_thread, daemon=True).start()
        return {"success": True, "message": "Download started..."}

    def start_progress_processing(self):
        def tick():
            import time
            while True:
                try:
                    for msg in self.downloader.process_progress_queue():
                        if self.window:
                            try:
                                percent = msg["percent"]
                                status = json.dumps(msg["status"])
                                details = json.dumps(msg["details"])
                                self.window.evaluate_js(
                                    f"""
                                    if (typeof updateProgress === 'function') {{
                                        updateProgress({percent}, {status}, {details});
                                    }}
                                    """
                                )
                            except Exception as e:
                                print(f"Error evaluating JS: {e}")
                except Exception as e:
                    print(f"Error in progress processing: {e}")
                time.sleep(0.1)

        if not self.progress_thread or not self.progress_thread.is_alive():
            self.progress_thread = threading.Thread(target=tick, daemon=True)
            self.progress_thread.start()

    def _escape_js_string(self, s):
        import json
        return json.dumps(str(s))[1:-1]

    def _js(self, code):
        if self.window:
            try:
                self.window.evaluate_js(code)
            except Exception as e:
                print(f"[ui] JS error: {e}")

    def get_video_info(self, url):
        result = self.downloader.get_video_info(clean_url(url))
        return result

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

    def open_download_folder(self):
        try:
            result = _open_platform(self.downloader.song_dir)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def change_download_folder(self):
        try:
            if not self.window:
                return {"success": False, "error": "Window not initialized"}
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
            return _open_platform(file_path)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def show_in_folder(self, file_path):
        try:
            result = _open_platform(file_path, reveal=True)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_app(self):
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
        return {"success": True}

    def minimize_app(self):
        if self.window:
            try:
                self.window.minimize()
            except Exception:
                pass
        return {"success": True}

    def toggle_fullscreen(self):
        if self.window:
            try:
                self.window.toggle_fullscreen()
            except Exception:
                pass
        return {"success": True}