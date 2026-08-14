"""Core YouTube audio downloader logic (UI-independent)."""
import json
import os
import queue
import re
from datetime import datetime
import yt_dlp

from utils import setup_authentication, format_file_size, format_duration, format_speed
from .validators import is_valid_youtube_url, is_playlist_url, clean_url, extract_playlist_id, normalize_playlist_url


class YouTubeAudioDownloader:
    """Handles YouTube audio downloads without any UI dependencies."""

    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        self.history_file = os.path.join(os.path.dirname(__file__), "..", "download_history.json")

        # 1. Set the default path first (needed as a fallback for load_settings)
        self.song_dir = os.path.join(output_dir, "songs")

        # 2. Load settings to check if the user has a custom folder saved
        self.settings = self.load_settings()

        # 3. Override with the custom folder if it exists in settings
        custom_folder = self.settings.get("download_folder")
        if custom_folder:
            self.song_dir = custom_folder

        # 4. FINALLY, create the directory.
        # This prevents creating the default 'downloads/songs' if a custom one is set!
        os.makedirs(self.song_dir, exist_ok=True)

        self.download_history = self.load_download_history()
        self.progress_queue = queue.Queue()

    # ===========================================================================
    # Settings & History Management
    # ===========================================================================
    def load_settings(self):
        settings_file = os.path.join(os.path.dirname(__file__), "..", "settings.json")
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
            with open(os.path.join(os.path.dirname(__file__), "..", "settings.json"),
                      "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

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
            return format_file_size(total)
        except Exception:
            return "0 MB"

    def get_last_download_time(self):
        if self.download_history:
            return self.download_history[0].get("timestamp", "Unknown")
        return "Never"

    # ===========================================================================
    # URL Validation & Info Helpers
    # ===========================================================================
    def get_video_info(self, url):
        url = clean_url(url)
        if is_playlist_url(url):
            return self.get_playlist_info(url)

        ydl_opts = {"quiet": True, "no_warnings": True}
        setup_authentication(ydl_opts)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            duration = info.get("duration", 0) or 0
            duration_str = format_duration(duration)

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

    def get_playlist_info(self, url):
        """Get metadata for a YouTube playlist (Guaranteed Thumbnail)."""
        playlist_url = normalize_playlist_url(url)

        # First try with extract_flat for speed
        ydl_opts_flat = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}
        setup_authentication(ydl_opts_flat)

        try:
            with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
                info = ydl.extract_info(playlist_url, download=False)

            entries = info.get("entries") or []
            video_count = info.get("playlist_count")
            if video_count is None:
                video_count = sum(1 for entry in entries if entry)

            description = info.get("description", "")
            if description:
                description = description[:200] + "..."

            # Get thumbnail - if not available, fetch full info to get it
            thumbnail = info.get("thumbnail", "")

            # If no thumbnail, make another request to get it
            if not thumbnail:
                ydl_opts_full = {"quiet": True, "no_warnings": True, "extract_flat": False}
                setup_authentication(ydl_opts_full)
                with yt_dlp.YoutubeDL(ydl_opts_full) as ydl:
                    full_info = ydl.extract_info(playlist_url, download=False)
                    thumbnail = full_info.get("thumbnail", "")

            return {
                "success": True,
                "data": {
                    "title": info.get("title", "Unknown Playlist"),
                    "author": info.get("uploader", "Unknown Author"),
                    "duration": f"{video_count} videos",
                    "upload_date": "Playlist",
                    "description": description,
                    "thumbnail": thumbnail,
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("view_count", 0),
                    "is_playlist": True,
                    "video_count": video_count,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===========================================================================
    # Core Download (Single Song)
    # ===========================================================================
    def download_audio(self, url, format="m4a", options=None):
        url = clean_url(url)
        if not is_valid_youtube_url(url):
            return {"success": False, "error": "Invalid YouTube URL"}

        options = options or {}

        # Route playlist URLs to playlist handler
        if is_playlist_url(url):
            return self.download_playlist(url, format, options)

        try:
            video_info = self.get_video_info(url)
            if not video_info["success"]:
                return video_info

            video_title = video_info["data"]["title"]
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)[:200]

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(self.song_dir, "%(id)s.%(ext)s"),
                "noprogress": False,
                "progress_with_newline": True,
                "progress_hooks": [self.progress_hook],
                "quiet": True,
                "no_warnings": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": format,
                        "preferredquality": "256" if options.get("high_quality", False) else "192",
                    },
                    {"key": "FFmpegMetadata"},
                ]
            }

            # Exact key names for thumbnail embedding
            if options.get("cover", True):
                ydl_opts["writethumbnail"] = True
                ydl_opts["postprocessors"].extend([
                    {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
                    {"key": "EmbedThumbnail", "already_have_thumbnail": False}
                ])

            setup_authentication(ydl_opts)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.extract_info(url, download=True)
                actual_file = ydl.prepare_filename(result)
                actual_file = os.path.splitext(actual_file)[0] + f".{format}"

            if not os.path.exists(actual_file):
                video_id = result.get("id", "")
                fallback = os.path.join(self.song_dir, f"{video_id}.{format}")
                if os.path.exists(fallback):
                    actual_file = fallback

            download_data = {
                "title": video_title,
                "format": format,
                "duration": video_info["data"]["duration"],
                "size": format_file_size(os.path.getsize(actual_file)) if actual_file and os.path.exists(actual_file) else "Unknown",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "file_path": actual_file,
                "thumbnail": video_info["data"]["thumbnail"],
                "url": url,
            }
            self.add_to_history(download_data)

            return {"success": True, "data": download_data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===========================================================================
    # Playlist Download
    # ===========================================================================
    def download_playlist(self, url, format="m4a", options=None):
        options = options or {}
        playlist_url = normalize_playlist_url(url)

        try:
            playlist_info = self.get_playlist_info(playlist_url)
            if not playlist_info["success"]:
                return playlist_info

            playlist_title = playlist_info["data"]["title"]
            video_count = playlist_info["data"]["video_count"]

            safe_title = re.sub(r'[<>:"/\\|?*]', '_', playlist_title)[:100]
            playlist_folder = os.path.join(self.song_dir, safe_title)
            os.makedirs(playlist_folder, exist_ok=True)

            print(f"Downloading playlist '{playlist_title}' with {video_count} videos...")

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(playlist_folder, "%(title)s_%(id)s.%(ext)s"),
                "noprogress": False,
                "progress_with_newline": True,
                "progress_hooks": [self.progress_hook],
                "quiet": False,
                "no_warnings": False,
                "ignoreerrors": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": format,
                        "preferredquality": "256" if options.get("high_quality", False) else "192",
                    },
                    {"key": "FFmpegMetadata"},
                ]
            }

            if options.get("cover", True):
                ydl_opts["writethumbnail"] = True
                ydl_opts["postprocessors"].extend([
                    {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
                    {"key": "EmbedThumbnail", "already_have_thumbnail": False}
                ])

            setup_authentication(ydl_opts)

            downloaded_count = 0
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    result = ydl.extract_info(playlist_url, download=True)
                    entries = result.get("entries") or []

                    # Add EACH SONG to history individually with its own thumbnail
                    for entry in entries:
                        if not entry or not isinstance(entry, dict):
                            continue

                        video_title = entry.get("title", "Unknown Title")
                        video_id = entry.get("id", "")
                        video_thumbnail = entry.get("thumbnail", "")
                        video_duration = entry.get("duration", 0) or 0

                        minutes, seconds = divmod(video_duration, 60)
                        hours, minutes = divmod(minutes, 60)
                        duration_str = f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes}:{seconds:02d}" if video_duration else "Unknown"

                        safe_video_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)[:100]
                        expected_filename = f"{safe_video_title}_{video_id}.{format}"
                        actual_file = os.path.join(playlist_folder, expected_filename)

                        if not os.path.exists(actual_file) and video_id:
                            for f in os.listdir(playlist_folder):
                                if video_id in f and f.endswith(f".{format}"):
                                    actual_file = os.path.join(playlist_folder, f)
                                    break

                        song_data = {
                            "title": video_title,
                            "format": format,
                            "duration": duration_str,
                            "size": format_file_size(os.path.getsize(actual_file)) if os.path.exists(actual_file) else "Unknown",
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "file_path": actual_file if os.path.exists(actual_file) else "",
                            "thumbnail": video_thumbnail,
                            "url": entry.get("webpage_url", url),
                            "playlist_title": playlist_title,
                        }
                        self.add_to_history(song_data)
                        downloaded_count += 1

                except Exception as e:
                    print(f"Error downloading playlist: {e}")
                    return {"success": False, "error": str(e)}

            if downloaded_count == 0:
                return {
                    "success": False,
                    "error": "No videos could be downloaded from this playlist.",
                }

            return {
                "success": True,
                "data": {
                    "title": f"{playlist_title} (Playlist - {downloaded_count}/{video_count} videos)",
                    "format": format,
                    "duration": f"{video_count} videos",
                    "size": self.calculate_storage_used(),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "file_path": playlist_folder,
                    "thumbnail": playlist_info["data"]["thumbnail"],
                    "url": url,
                    "is_playlist": True,
                    "video_count": downloaded_count,
                },
                "message": f"Downloaded {downloaded_count}/{video_count} videos to {playlist_folder}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ===========================================================================
    # Progress Hook (callable, no self.window dependency)
    # ===========================================================================
    def progress_hook(self, d):
        """Progress callback that puts progress data into a queue for UI thread."""
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes", 0)
            speed = d.get("speed", 0)
            eta = d.get("eta", 0)

            percent = (downloaded / total * 100) if total and total > 0 else 0

            speed_str = format_speed(speed)
            downloaded_str = format_file_size(downloaded)
            total_str = format_file_size(total) if total else "0 KB"
            eta_str = f"{int(eta // 60):02d}:{int(eta % 60):02d}" if eta else "--:--"

            details = f"Speed: {speed_str} | Downloaded: {downloaded_str} / {total_str} | ETA: {eta_str}"
            self.progress_queue.put(("progress", percent, f"Downloading... {percent:.1f}%", details))

        elif d["status"] == "finished":
            self.progress_queue.put(("progress", 100, "Processing audio...", "Converting format..."))

    def process_progress_queue(self):
        """Process items from the progress queue (called by UI layer)."""
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if msg[0] == "progress":
                    # Return the data for the UI layer to handle
                    percent, status, details = msg[1], msg[2], msg[3]
                    yield {"type": "progress", "percent": percent, "status": status, "details": details}
                self.progress_queue.task_done()
        except queue.Empty:
            pass

    # ===========================================================================
    # Utilities
    # ===========================================================================
    def find_downloaded_file(self, video_title, format):
        """Find a downloaded file by video title and format."""
        try:
            clean_title = re.sub(r'[<>:"/\\|?*]', '_', video_title)[:150]
            for filename in os.listdir(self.song_dir):
                if filename.endswith(f".{format}"):
                    if clean_title in filename or video_title in filename:
                        return os.path.join(self.song_dir, filename)
            return None
        except Exception:
            return None

    def get_actual_file_size(self, file_path):
        """Get human-readable file size for a downloaded file."""
        if file_path and os.path.exists(file_path):
            return format_file_size(os.path.getsize(file_path))
        return "Unknown size"