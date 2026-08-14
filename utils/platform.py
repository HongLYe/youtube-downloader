"""Cross-platform file and folder operations."""
import os
import subprocess
import sys


def open_file(path, reveal=False):
    """Open a file or folder in the system file explorer.

    Args:
        path: Path to file or folder
        reveal: If True, reveal the file in its folder; if False, open the folder

    Returns:
        dict with 'success' key indicating operation result
    """
    try:
        if sys.platform == "win32":
            if reveal:
                subprocess.Popen(f'explorer /select, "{path}"')
            else:
                os.startfile(path)
        elif sys.platform == "darwin":
            cmd = ["open", "-R", path] if reveal else ["open", path]
            subprocess.Popen(cmd)
        else:
            # Linux and other Unix-like systems
            subprocess.Popen(["xdg-open", os.path.dirname(path) if reveal else path])
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}