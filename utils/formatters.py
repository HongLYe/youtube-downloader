"""Formatting utility functions for file sizes, speeds, and durations."""


def format_file_size(size_bytes):
    """Convert bytes to human-readable format (B, KB, MB, GB)."""
    if not size_bytes:
        return "Unknown size"
    try:
        total = float(size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if total < 1024.0:
                return f"{total:.1f} {unit}"
            total /= 1024.0
        return f"{total:.1f} GB"
    except (TypeError, ValueError):
        return "Unknown size"


def format_speed(speed):
    """Convert bytes/s to human-readable speed string."""
    if speed is None or speed < 0:
        return "-- KB/s"
    try:
        speed = float(speed)
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed / 1024:.1f} KB/s"
        else:
            return f"{speed / (1024 * 1024):.1f} MB/s"
    except (TypeError, ValueError):
        return "-- KB/s"


def format_duration(duration_seconds):
    """Convert seconds to human-readable duration string (MM:SS or H:MM:SS)."""
    if not duration_seconds:
        return "Unknown"
    try:
        duration = int(duration_seconds)
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    except (TypeError, ValueError):
        return "Unknown"