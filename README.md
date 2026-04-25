# YouTube Audio Downloader

A modern, cross-platform desktop application for downloading audio from YouTube videos. Available in both GUI (CustomTkinter) and webview-based versions.

## Features

- 🎵 **YouTube Audio Extraction**: Download audio from YouTube videos in MP3 format
- 🎨 **Modern UI**: Clean, macOS-inspired interface with dark/light mode support
- 📀 **Metadata Support**: Automatically embed cover art and metadata in downloaded files
- 📁 **File Organization**: Organize downloads by artist/album structure
- 🔒 **Cookie Authentication**: Supports browser cookie integration for age-restricted content
- ⚡ **High Quality**: Configurable audio quality options
- 📊 **Download History**: Track your downloads with history management

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd youtube-downloader
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### GUI Version (Recommended)

Run the CustomTkinter-based GUI application:

```bash
python youtube_mp3_gui.py
```

**Features:**
- Modern, responsive interface
- System theme detection (dark/light mode)
- Real-time download progress
- Settings management

### WebView Version

Run the webview-based application:

```bash
python main.py
```

**Features:**
- Cross-platform web-based UI
- Built-in HTTP server
- Browser-like interface

## Configuration

Settings are stored in `settings.json`:

```json
{
  "auto_start": true,
  "download_cover": true,
  "add_metadata": true,
  "high_quality": false,
  "organize_files": true,
  "download_folder": "C:\\Users\\YourName\\Music",
  "total_downloads": 0,
  "storage_used": "0 MB"
}
```

### Settings Options

| Setting | Description | Default |
|---------|-------------|---------|
| `auto_start` | Auto-start downloads | `true` |
| `download_cover` | Download album artwork | `true` |
| `add_metadata` | Embed metadata in files | `true` |
| `high_quality` | Use highest audio quality | `false` |
| `organize_files` | Organize by artist/album | `true` |
| `download_folder` | Output directory | User-specific |

## Cookie Setup (Optional)

For age-restricted videos, you can export cookies from your browser:

1. Install a browser extension like "Get cookies.txt LOCALLY"
2. Export cookies from youtube.com
3. Save as `www.youtube.com_cookies.txt` in the project directory

The application will automatically detect and use these cookies.

## Dependencies

- **pywebview** (>=4.4.1): Cross-platform webview library
- **yt-dlp** (>=2024.10.0): YouTube video downloader
- **requests** (>=2.32.3): HTTP library
- **customtkinter** (>=5.2.0): Modern GUI framework

## Project Structure

```
youtube-downloader/
├── main.py                 # WebView-based application
├── youtube_mp3_gui.py      # CustomTkinter GUI application
├── requirements.txt        # Python dependencies
├── settings.json          # Application settings
├── download_history.json  # Download history tracking
├── ui/                     # Web interface files
│   ├── index.html         # Main HTML page
│   ├── script.js          # Frontend JavaScript
│   └── styles.css         # Styling
└── README.md              # This file
```

## Platform Support

- ✅ Windows 10/11
- ✅ macOS
- ✅ Linux

## Troubleshooting

### Age-Restricted Videos
If you encounter errors with age-restricted videos, set up browser cookies as described in the [Cookie Setup](#cookie-setup-optional) section.

### Download Failures
- Ensure you have a stable internet connection
- Update yt-dlp: `pip install --upgrade yt-dlp`
- Check if the video is available in your region

### GUI Issues
- On Linux, ensure you have tkinter installed: `sudo apt-get install python3-tk`
- On macOS, you may need to grant screen recording permissions

## License

This project is provided as-is for educational purposes. Please respect YouTube's Terms of Service and copyright laws when using this application.

## Disclaimer

This tool is intended for downloading content that you have the right to download. The developers are not responsible for any misuse of this software or copyright infringement.

