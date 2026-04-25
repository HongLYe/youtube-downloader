// ===========================================================================
// YouTube Audio Downloader — Frontend (macOS style)
// ===========================================================================

let currentFormat = 'm4a';
let downloadOptions = { cover: true, metadata: true };
let darkMode = false;

// Detect dark mode
function detectDarkMode() {
    darkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
    window.matchMedia('(prefers-color-scheme: dark)')
        .addEventListener('change', detectDarkMode);
}

document.addEventListener('DOMContentLoaded', () => {
    detectDarkMode();
    initializeNavigation();
    initializeOptionSelection();
    initializeEventListeners();
    loadSettings();
    updateDownloadStats();
    loadDownloadHistory();
    updateStorageFooter();
});

// ===========================================================================
// Navigation
// ===========================================================================
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.section');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const target = item.getAttribute('data-section');

            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(s => s.classList.toggle('active', s.id === target));

            const titleEl = document.getElementById('toolbar-title');
            const labels = {
                'download-section': 'Download Audio',
                'history-section': 'Download History',
                'preferences-section': 'Preferences',
                'folder-section': 'Download Folder',
                'about-section': 'About',
            };
            if (titleEl && labels[target]) titleEl.textContent = labels[target];

            if (target === 'history-section') loadDownloadHistory();
            if (target === 'preferences-section') loadSettings();
            if (target === 'folder-section') loadSettings();
            if (target === 'download-section') updateStorageFooter();
        });
    });
}

// ===========================================================================
// Option cards
// ===========================================================================
function initializeOptionSelection() {
    document.querySelectorAll('.option-card').forEach(card => {
        card.addEventListener('click', () => {
            const fmt = card.getAttribute('data-format');
            const opt = card.getAttribute('data-option');

            if (fmt) {
                document.querySelectorAll('.option-card[data-format]').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                currentFormat = fmt;
                saveSettings();
            } else if (opt) {
                card.classList.toggle('selected');
                downloadOptions[opt] = card.classList.contains('selected');
                saveSettings();
            }
        });
    });
}

// ===========================================================================
// Event listeners
// ===========================================================================
function initializeEventListeners() {
    // Paste button
    document.getElementById('paste-btn')?.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            document.getElementById('url-input').value = text;
            if (isValidYouTubeUrl(text)) fetchVideoInfo(text);
            toast('Pasted from clipboard', 'success');
        } catch {
            toast('Unable to read clipboard', 'error');
        }
    });

    // URL input
    document.getElementById('url-input')?.addEventListener('input', function () {
        const url = this.value.trim();
        if (isValidYouTubeUrl(url)) {
            fetchVideoInfo(url);
        } else {
            hideVideoPreview();
        }
    });

    // Download button
    document.getElementById('download-btn')?.addEventListener('click', () => {
        const url = document.getElementById('url-input').value.trim();
        if (!url) return toast('Please enter a YouTube URL', 'error');
        if (!isValidYouTubeUrl(url)) return toast('Please enter a valid YouTube URL', 'error');
        startDownload(url, currentFormat, downloadOptions);
    });

    // Open folder
    document.getElementById('download-btn')?.closest('.section')
        ?.querySelector('#download-btn'); // already handled above

    document.querySelectorAll('.content .section').forEach(section => {
        const folderBtn = section.querySelector('#open-folder-btn, .open-folder-btn');
        // We handle below
    });

    // Add open-folder click handler to any button with that id
    document.getElementById('download-btn')?.parentElement?.closest('.section');
}

// Re-build event listeners properly for buttons that exist in index.html
(function bindButtons() {
    // Open folder button
    const openFolder = () => {
        if (window.pywebview) {
            window.pywebview.api.open_download_folder().then(r => {
                if (!r.success) toast('Could not open folder: ' + r.error, 'error');
            });
        }
    };
    document.addEventListener('click', e => {
        const btn = e.target.closest('#open-folder-btn, .open-folder-btn');
        if (btn) openFolder();
    });

    // Change folder button
    document.addEventListener('click', e => {
        if (e.target.closest('#change-folder-btn') && window.pywebview) {
            window.pywebview.api.change_download_folder().then(r => {
                if (r.success) {
                    document.getElementById('download-folder-path').textContent = r.folder;
                    toast('Download folder updated', 'success');
                } else {
                    toast('Could not change folder: ' + r.error, 'error');
                }
            });
        }
    });

    // Clear history button
    document.addEventListener('click', e => {
        if (e.target.closest('#clear-history-btn') && confirm('Clear all download history?')) {
            if (window.pywebview) {
                window.pywebview.api.clear_download_history().then(() => {
                    loadDownloadHistory();
                    updateDownloadStats();
                    updateStorageFooter();
                    toast('History cleared', 'success');
                });
            }
        }
    });
})();

// Preferences toggle listeners
['auto-start', 'download-cover', 'add-metadata', 'high-quality', 'organize-files']
    .forEach(id => {
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById(id)?.addEventListener('change', saveSettings);
        });
    });

// ===========================================================================
// URL validation
// ===========================================================================
function isValidYouTubeUrl(url) {
    return /^(https?:\/\/)?(www\.|m\.)?(youtube\.com|youtu\.?be|music\.youtube\.com)\/.+$/.test(url);
}

// ===========================================================================
// Video info
// ===========================================================================
function fetchVideoInfo(url) {
    if (!window.pywebview) return;
    window.pywebview.api.get_video_info(url).then(info => {
        if (info.success) {
            displayVideoInfo(info.data);
        } else {
            toast('Could not fetch video info: ' + info.error, 'error');
            hideVideoPreview();
        }
    }).catch(() => {
        toast('Error fetching video info', 'error');
        hideVideoPreview();
    });
}

function displayVideoInfo(v) {
    const preview = document.getElementById('video-preview-card');
    const thumb = document.getElementById('video-thumbnail');
    const title = document.getElementById('video-title');
    const author = document.getElementById('video-author');
    const duration = document.getElementById('video-duration');
    const date = document.getElementById('video-date');
    const description = document.getElementById('video-description');

    if (!preview) return;

    if (v.thumbnail) {
        thumb.style.backgroundImage = `url('${v.thumbnail}')`;
        thumb.innerHTML = '';
    } else {
        thumb.style.backgroundImage = '';
        thumb.innerHTML = '<i class="fab fa-youtube"></i>';
    }

    if (title) title.textContent = v.title || 'Unknown Title';
    if (author) { author.innerHTML = `<i class="fas fa-user"></i> ${v.author || 'Unknown'}`; }
    if (duration) { duration.innerHTML = `<i class="fas fa-clock"></i> ${v.duration || 'Unknown'}`; }
    if (date) { date.innerHTML = `<i class="fas fa-calendar"></i> ${v.upload_date || 'Unknown'}`; }
    if (description) description.textContent = v.description || 'No description available';

    preview.style.display = 'block';
}

function hideVideoPreview() {
    const p = document.getElementById('video-preview-card');
    if (p) p.style.display = 'none';
}

// ===========================================================================
// Download
// ===========================================================================
function startDownload(url, format, options) {
    const btn = document.getElementById('download-btn');
    const card = document.getElementById('progress-card');
    if (!btn || !card) return;

    card.style.display = 'block';
    btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Downloading&#x2026;';
    btn.classList.add('downloading');
    btn.disabled = true;

    updateProgress(0, 'Starting&#x2026;', 'Speed: 0 KB/s | Downloaded: 0 KB / 0 KB | ETA: --:--');

    if (window.pywebview) {
        window.pywebview.api.download_audio(url, format, options).then(r => {
            if (!r.success) {
                toast('Download failed: ' + r.error, 'error');
                resetDownloadButton();
            }
        }).catch(() => {
            toast('Download error', 'error');
            resetDownloadButton();
        });
    }
}

function updateProgress(percent, status, details) {
    const bar = document.getElementById('progress-bar');
    const pctEl = document.getElementById('progress-percent');
    const lblEl = document.getElementById('progress-label');
    const detEl = document.getElementById('progress-details');

    if (bar) bar.style.width = `${Math.min(percent, 100)}%`;
    if (pctEl) pctEl.textContent = `${Math.round(Math.min(percent, 100))}%`;
    if (lblEl) lblEl.textContent = status;
    if (detEl) detEl.textContent = details;
}

function addToHistory(downloadData) {
    loadDownloadHistory();
    updateDownloadStats();
    updateStorageFooter();
    resetDownloadButton();
}

function resetDownloadButton() {
    const btn = document.getElementById('download-btn');
    if (!btn) return;
    btn.innerHTML = '<i class="fas fa-download"></i> Download Audio';
    btn.classList.remove('downloading');
    btn.disabled = false;
}

// ===========================================================================
// Stats & History
// ===========================================================================
function updateDownloadStats() {
    if (!window.pywebview) return;
    window.pywebview.api.get_download_stats().then(stats => {
        if (document.getElementById('total-downloads'))
            document.getElementById('total-downloads').textContent = stats.total_downloads;
        if (document.getElementById('storage-used'))
            document.getElementById('storage-used').textContent = stats.storage_used;
        if (document.getElementById('last-download'))
            document.getElementById('last-download').textContent = stats.last_download;
    });
}

function updateStorageFooter() {
    if (!window.pywebview) return;
    window.pywebview.api.get_download_stats().then(stats => {
        const el = document.getElementById('status-storage');
        if (el) el.textContent = `${stats.total_downloads} items  ·  ${stats.storage_used}`;
    });
}

function loadDownloadHistory() {
    if (!window.pywebview) return;
    window.pywebview.api.get_download_history().then(history => {
        displayDownloadHistory(history);
    }).catch(() => {});
}

function displayDownloadHistory(history) {
    const list = document.getElementById('history-list');
    if (!list) return;

    if (!history || history.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-clock-rotate-left"></i>
                <p>No downloads yet</p>
            </div>`;
        return;
    }

    list.innerHTML = history.map(item => `
        <div class="history-item">
            <div class="history-thumb" style="${item.thumbnail ? `background-image:url('${item.thumbnail}')` : ''}">
                ${!item.thumbnail ? '<i class="fas fa-music"></i>' : ''}
            </div>
            <div class="history-info">
                <div class="history-title">${item.title || 'Unknown'}</div>
                <div class="history-details">
                    ${(item.duration || 'Unknown')} · ${(item.format || 'm4a').toUpperCase()} · ${(item.size || 'Unknown')} · ${(item.timestamp || 'Unknown')}
                </div>
            </div>
            <div class="history-actions">
                <button class="history-btn" onclick="playAudio('${(item.file_path || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')" title="Play">
                    <i class="fas fa-play"></i>
                </button>
                <button class="history-btn" onclick="showInFolder('${(item.file_path || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'")}')" title="Show in folder">
                    <i class="fas fa-folder-open"></i>
                </button>
            </div>
        </div>`).join('');
}

// ===========================================================================
// Settings
// ===========================================================================
function loadSettings() {
    if (!window.pywebview) return;
    window.pywebview.api.get_settings().then(s => {
        if (document.getElementById('auto-start'))
            document.getElementById('auto-start').checked = s.auto_start !== false;
        if (document.getElementById('download-cover'))
            document.getElementById('download-cover').checked = s.download_cover !== false;
        if (document.getElementById('add-metadata'))
            document.getElementById('add-metadata').checked = s.add_metadata !== false;
        if (document.getElementById('high-quality'))
            document.getElementById('high-quality').checked = s.high_quality || false;
        if (document.getElementById('organize-files'))
            document.getElementById('organize-files').checked = s.organize_files !== false;
        if (s.download_folder && document.getElementById('download-folder-path'))
            document.getElementById('download-folder-path').textContent = s.download_folder;

        // Update option cards
        document.querySelectorAll('.option-card[data-format]').forEach(c => {
            c.classList.toggle('selected', c.getAttribute('data-format') === currentFormat);
        });
        ['cover', 'metadata'].forEach(opt => {
            const card = document.querySelector(`.option-card[data-option="${opt}"]`);
            if (card) card.classList.toggle('selected', s[`download_${opt}`] !== false);
        });
    });
}

function saveSettings() {
    const s = {
        auto_start: document.getElementById('auto-start')?.checked ?? true,
        download_cover: document.getElementById('download-cover')?.checked ?? true,
        add_metadata: document.getElementById('add-metadata')?.checked ?? true,
        high_quality: document.getElementById('high-quality')?.checked ?? false,
        organize_files: document.getElementById('organize-files')?.checked ?? true,
    };
    if (window.pywebview) window.pywebview.api.save_settings(s);
}

// ===========================================================================
// Playback helpers
// ===========================================================================
function playAudio(filePath) {
    if (window.pywebview) window.pywebview.api.play_audio(filePath);
}

function showInFolder(filePath) {
    if (window.pywebview) window.pywebview.api.show_in_folder(filePath);
}

// ===========================================================================
// Toasts
// ===========================================================================
function toast(message, type = 'info') {
    const icons = { success: 'check-circle', error: 'exclamation-circle', info: 'info-circle' };
    document.querySelectorAll('.toast').forEach(t => t.remove());

    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<i class="fas fa-${icons[type] || icons.info}"></i><span>${message}</span>`;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

// ===========================================================================
// Search overlay
// ===========================================================================
function toggleSearch() {
    const overlay = document.getElementById('search-overlay');
    const input = document.getElementById('search-input');
    if (!overlay) return;
    const visible = overlay.classList.toggle('visible');
    if (visible && input) input.focus();
}

// Titlebar search icon
document.addEventListener('DOMContentLoaded', () => {
    const titlebarSearch = document.getElementById('titlebar-search-btn');
    if (titlebarSearch) titlebarSearch.addEventListener('click', () => toggleSearch());
});

// Close search on Escape
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        const overlay = document.getElementById('search-overlay');
        if (overlay && overlay.classList.contains('visible')) {
            e.preventDefault();
            overlay.classList.remove('visible');
        }
    }
    // Cmd/Ctrl+F: toggle search
    if ((e.metaKey || e.ctrlKey) && e.key === 'f') {
        e.preventDefault();
        toggleSearch();
    }
});

// ===========================================================================
// Expose for Python → JS calls
// ===========================================================================
window.updateProgress = updateProgress;
window.showError = (msg) => toast(msg, 'error');
window.showSuccess = (msg) => toast(msg, 'success');
window.playAudio = playAudio;
window.showInFolder = showInFolder;
window.addToHistory = addToHistory;
window.updateDownloadStats = updateDownloadStats;
