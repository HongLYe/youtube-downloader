"""Authentication setup for YouTube downloads."""
import pathlib


def setup_authentication(ydl_opts: dict):
    """Configure yt-dlp options to use cookies for authentication if available.

    Checks for a cookie file in the script's directory and adds it to ydl_opts
    if found and non-empty.
    """
    script_dir = pathlib.Path(__file__).parent.parent
    cookie_file = script_dir / "www.youtube.com_cookies.txt"
    if cookie_file.exists() and cookie_file.stat().st_size > 0:
        ydl_opts["cookiefile"] = str(cookie_file)
        print("[auth] Using provided cookie file for authentication")
    else:
        print("[auth] Running without cookies. Most videos will download successfully.")