# Developer Guide

Version: 1.1.0

This project is a desktop application for downloading audio from YouTube. It uses Python for the backend and a web-based UI rendered through pywebview.

## Quick overview

- main.py starts the app and creates the window.
- api/bridge.py exposes Python functions to the frontend.
- core/downloader.py performs URL validation, metadata lookup, downloads, playlist handling, and progress reporting.
- ui/ contains the HTML, CSS, and JavaScript for the desktop interface.
- utils/ contains helper functions such as authentication and formatting.

## Main flow

1. The app starts from main.py.
2. The frontend is loaded from ui/index.html.
3. JavaScript calls Python functions through pywebview.
4. The backend uses yt-dlp to download audio and FFmpeg to convert it.
5. Results are written to the chosen download folder and saved in download history.

## Important files

- main.py: application entry point
- api/bridge.py: bridge between UI and backend
- core/downloader.py: main business logic
- core/validators.py: URL checks and playlist utilities
- ui/script.js: UI interactions and request handling
- settings.json: saved preferences
- download_history.json: log of previous downloads

## How to run locally

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.\.venv\Scripts\activate   # Windows
python -m pip install -r requirements.txt
python main.py
```

## Where to edit

- Add new UI behavior in ui/script.js
- Add or change download logic in core/downloader.py
- Expose new capabilities to the UI in api/bridge.py
- Update saved preferences in core/downloader.py and settings.json

## Notes for contributors

- FFmpeg must be installed for audio conversion.
- The app expects a valid YouTube URL or playlist URL.
- Cookie support is optional and uses www.youtube.com_cookies.txt if present.
- Download history is stored locally in download_history.json.

## Suggested first changes

- Improve the UI text or layout in ui/index.html and ui/styles.css
- Add a new download setting in the preferences flow
- Extend the history view with extra metadata
- Improve error handling for failed downloads
