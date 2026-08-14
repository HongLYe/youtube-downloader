# YouTube Audio Downloader

Current version: 1.1.0

A desktop app for downloading audio from YouTube videos and playlists in MP3 or M4A format. The interface is a modern web-based UI powered by Python and pywebview, and it includes download history, progress updates, theme support, and optional cookie-based authentication for restricted content.

## What this project does

- Download a single YouTube video as audio
- Download an entire playlist
- Save files to a chosen folder
- Embed cover art and metadata when available
- Track previous downloads and storage usage
- Support optional browser cookies for restricted videos

## Requirements

Before installing, make sure you have:

- Python 3.9 or newer
- pip
- FFmpeg installed and available in your PATH

### FFmpeg installation

- Windows: install FFmpeg and add it to PATH, or use a package manager such as winget
- macOS: brew install ffmpeg
- Linux: sudo apt install ffmpeg

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd "yt - UI update"
```

2. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

3. Install Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

4. Start the application:

```bash
python main.py
```

## How to use it

### Single video download

1. Open the app.
2. Paste a YouTube video URL into the main input field.
3. Choose a format such as MP3 or M4A.
4. Select any extra options like cover art or metadata.
5. Click Download.

### Playlist download

1. Open the Playlist tab.
2. Paste a YouTube playlist URL.
3. Click Download Playlist.
4. The app will save each track into a playlist folder.

### Settings and folder selection

- Use the Preferences section to change quality, metadata, and cover options.
- Use the Download Folder section to choose where files are stored.
- Download history and stats are shown in the History section.

## Project structure

```text
.
├── api/
│   └── bridge.py           # Connects the UI to the Python backend
├── core/
│   ├── downloader.py       # Main download, playlist, and progress logic
│   └── validators.py       # URL validation helpers
├── ui/
│   ├── index.html          # Main UI layout
│   ├── script.js           # Frontend behavior and API calls
│   └── styles.css          # Styling for the desktop UI
├── utils/
│   ├── auth.py             # Optional cookie authentication support
│   └── formatters.py       # Formatting helpers for sizes/durations
├── main.py                 # Entry point for the app
├── requirements.txt        # Python dependencies
├── settings.json           # Saved preferences
├── download_history.json   # Download history data
├── README.md               # Project overview
└── DEVELOPER_GUIDE.md      # Quick guide for contributors
```

## Optional cookie setup

If you run into age-restricted or login-gated videos, place a cookies file named `www.youtube.com_cookies.txt` in the project root. The app will automatically use it if the file is present and not empty.

## Troubleshooting

- If downloads fail, confirm that FFmpeg is installed and available in PATH.
- If a video is blocked, try adding browser cookies.
- If the app does not start, make sure the Python dependencies were installed successfully.
- If a download folder cannot be changed, confirm the selected location is writable.

## Developer guide

For a faster introduction to the codebase, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

## License

This project is provided for educational and personal use. Please respect YouTube's Terms of Service and local copyright laws.

