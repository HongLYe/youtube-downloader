"""URL validation and playlist URL manipulation functions."""
import re


# Precompiled regex patterns for performance
_PLAYLIST_ID_RE = re.compile(r'[?&]list=([A-Za-z0-9_-]+)')
_PLAYLIST_PAGE_RE = re.compile(
    r'(https?://)?((www|music)\.)?youtube\.com/playlist\?list=[A-Za-z0-9_-]+'
)
_VIDEO_URL_RE = re.compile(
    r'(https?:\/\/)?(www\.)?'
    r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
    r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
)


def extract_playlist_id(url):
    """Extract the playlist ID from a YouTube URL."""
    if not url:
        return None
    match = _PLAYLIST_ID_RE.search(url)
    return match.group(1) if match else None


def normalize_playlist_url(url):
    """Normalize a playlist URL to standard format."""
    if not url:
        return url
    playlist_id = extract_playlist_id(url)
    if playlist_id:
        return f"https://www.youtube.com/playlist?list={playlist_id}"
    if _PLAYLIST_PAGE_RE.search(url):
        return url
    return url


def is_playlist_url(url):
    """Check if the URL is a YouTube playlist."""
    if not url:
        return False
    if _PLAYLIST_PAGE_RE.search(url):
        return True
    return bool(extract_playlist_id(url))


def is_valid_youtube_url(url):
    """Validate if the URL is a valid YouTube video or playlist URL."""
    if not url:
        return False
    return bool(
        _VIDEO_URL_RE.match(url)
        or _PLAYLIST_PAGE_RE.search(url)
        or extract_playlist_id(url)
    )


def clean_url(url):
    """Strip whitespace from URL."""
    return (url or "").strip()