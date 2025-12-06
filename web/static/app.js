/**
 * AnimePahe Web Downloader - Main Application
 */

// ============================================
// State Management
// ============================================

const state = {
    currentView: 'search',
    searchResults: [],
    selectedAnime: null,
    episodes: [],
    selectedEpisodes: new Set(),
    downloadQueue: {},
    settings: {
        downloadPath: '',
        maxWorkers: 4,
        defaultQuality: 0
    },
    ws: null,
    wsReconnectAttempts: 0
};

// Load settings from localStorage
function loadSettings() {
    const saved = localStorage.getItem('animepahe_settings');
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            state.settings = { ...state.settings, ...parsed };
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    }
}

// Save settings to localStorage
function saveSettingsToStorage() {
    localStorage.setItem('animepahe_settings', JSON.stringify(state.settings));
}

// ============================================
// API Functions
// ============================================

const API = {
    baseUrl: '/api',

    async search(query) {
        const res = await fetch(`${this.baseUrl}/search?q=${encodeURIComponent(query)}`);
        if (!res.ok) throw new Error('Search failed');
        return res.json();
    },

    async getAnimeDetails(session) {
        const res = await fetch(`${this.baseUrl}/anime/${session}`);
        if (!res.ok) throw new Error('Failed to get anime details');
        return res.json();
    },

    async getEpisodes(session, allPages = true) {
        const res = await fetch(`${this.baseUrl}/anime/${session}/episodes?all_pages=${allPages}`);
        if (!res.ok) throw new Error('Failed to get episodes');
        return res.json();
    },

    async startDownload(animeSession, animeTitle, episodeSessions, resolution) {
        const res = await fetch(`${this.baseUrl}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                anime_session: animeSession,
                anime_title: animeTitle,
                episodes: episodeSessions,
                resolution: resolution
            })
        });
        if (!res.ok) throw new Error('Failed to start download');
        return res.json();
    },

    async batchDownload(animeSession, animeTitle, startEp, endEp, resolution) {
        const res = await fetch(`${this.baseUrl}/download/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                anime_session: animeSession,
                anime_title: animeTitle,
                start_episode: startEp,
                end_episode: endEp,
                resolution: resolution
            })
        });
        if (!res.ok) throw new Error('Failed to start batch download');
        return res.json();
    },

    async getQueueStatus() {
        const res = await fetch(`${this.baseUrl}/queue`);
        if (!res.ok) throw new Error('Failed to get queue status');
        return res.json();
    },

    async retryFailed() {
        const res = await fetch(`${this.baseUrl}/queue/retry`, { method: 'POST' });
        if (!res.ok) throw new Error('Failed to retry downloads');
        return res.json();
    },

    async clearCompleted() {
        const res = await fetch(`${this.baseUrl}/queue/clear`, { method: 'POST' });
        if (!res.ok) throw new Error('Failed to clear completed');
        return res.json();
    },

    async cancelDownload(taskId) {
        const res = await fetch(`${this.baseUrl}/queue/${taskId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error('Failed to cancel download');
        return res.json();
    },

    async getSettings() {
        const res = await fetch(`${this.baseUrl}/settings`);
        if (!res.ok) throw new Error('Failed to get settings');
        return res.json();
    },

    async updateSettings(settings) {
        const res = await fetch(`${this.baseUrl}/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (!res.ok) throw new Error('Failed to update settings');
        return res.json();
    }
};

// ============================================
// WebSocket Connection
// ============================================

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/progress`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('WebSocket connected');
        state.wsReconnectAttempts = 0;
    };

    state.ws.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleWSMessage(message);
        } catch (e) {
            console.error('Failed to parse WebSocket message:', e);
        }
    };

    state.ws.onclose = () => {
        console.log('WebSocket disconnected');
        // Attempt to reconnect
        if (state.wsReconnectAttempts < 5) {
            state.wsReconnectAttempts++;
            setTimeout(connectWebSocket, 2000 * state.wsReconnectAttempts);
        }
    };

    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    // Send ping every 20 seconds to keep connection alive
    setInterval(() => {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            state.ws.send(JSON.stringify({ type: 'ping' }));
        }
    }, 20000);
}

function handleWSMessage(message) {
    switch (message.type) {
        case 'progress':
            updateDownloadProgress(message.task);
            break;
        case 'status':
            updateQueueStatus(message.queue);
            break;
        case 'heartbeat':
        case 'pong':
            // Connection alive
            break;
        default:
            console.log('Unknown message type:', message.type);
    }
}

// ============================================
// UI Update Functions
// ============================================

function switchView(viewName) {
    state.currentView = viewName;

    // Update nav buttons
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });

    // Update views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.toggle('active', view.id === `${viewName}-view`);
    });

    // Load view-specific data
    if (viewName === 'downloads') {
        refreshQueueStatus();
    } else if (viewName === 'settings') {
        loadSettingsUI();
    }
}

function showSearchLoader(show) {
    document.getElementById('search-loader').classList.toggle('active', show);
}

function renderSearchResults(results) {
    const container = document.getElementById('search-results');

    if (!results || results.length === 0) {
        container.innerHTML = '<div class="no-results">No anime found</div>';
        container.classList.add('active');
        return;
    }

    container.innerHTML = results.map(anime => `
        <div class="search-result-item" data-session="${anime.session}" data-title="${escapeHtml(anime.title)}" data-poster="${escapeHtml(anime.poster || '')}">
            <img class="result-poster" src="${anime.poster || ''}" alt="${escapeHtml(anime.title)}" 
                 onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 140%22%3E%3Crect fill=%22%231a1a1a%22 width=%22100%22 height=%22140%22/%3E%3Ctext x=%2250%22 y=%2270%22 text-anchor=%22middle%22 fill=%22%23555%22 font-size=%2212%22%3ENo Image%3C/text%3E%3C/svg%3E'">
            <div class="result-info">
                <div class="result-title">${escapeHtml(anime.title)}</div>
                <div class="result-meta">
                    <span>${anime.type || 'TV'}</span>
                    <span>${anime.episodes || '?'} eps</span>
                    <span>${anime.year || ''}</span>
                    <span>${anime.status || ''}</span>
                </div>
            </div>
        </div>
    `).join('');

    container.classList.add('active');

    // Add click handlers
    container.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => selectAnime(item.dataset.session, item.dataset.title, item.dataset.poster));
    });
}

async function selectAnime(session, title, poster) {
    try {
        showToast('info', 'Loading...', 'Fetching anime details');

        // Hide search results
        document.getElementById('search-results').classList.remove('active');
        document.getElementById('search-input').value = title;

        // Fetch details and episodes
        const [details, episodesData] = await Promise.all([
            API.getAnimeDetails(session),
            API.getEpisodes(session, true)
        ]);

        state.selectedAnime = { session, title, poster, ...details };
        state.episodes = episodesData.episodes;
        state.selectedEpisodes.clear();

        // Render anime info
        renderAnimeInfo(state.selectedAnime);

        // Render episodes
        renderEpisodes(state.episodes);

        // Show anime panel
        document.querySelector('.search-section').style.display = 'none';
        document.getElementById('anime-panel').classList.add('active');

        updateSelectionCount();

    } catch (error) {
        console.error('Failed to load anime:', error);
        showToast('error', 'Error', 'Failed to load anime details');
    }
}

function renderAnimeInfo(anime) {
    const container = document.getElementById('anime-info');

    const genresHtml = (anime.genres || []).map(g => `<span class="meta-tag">${g}</span>`).join('');
    const synopsis = anime.synopsis ? `<div class="anime-synopsis">${escapeHtml(anime.synopsis)}</div>` : '';
    const altTitles = [anime.english_title, anime.japanese_title].filter(t => t && t !== anime.title).join(' • ');

    container.innerHTML = `
        <div class="detail-header">
            <img class="detail-poster" src="${anime.poster || ''}" alt="${escapeHtml(anime.title)}"
                 onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 180 260%22%3E%3Crect fill=%22%231a1a25%22 width=%22180%22 height=%22260%22/%3E%3Ctext x=%2290%22 y=%22130%22 text-anchor=%22middle%22 fill=%22%2371717a%22 font-size=%2216%22%3ENo Image%3C/text%3E%3C/svg%3E'">
            <div class="detail-content">
                <h1 class="anime-title" style="font-size: 2rem; white-space: normal;">${escapeHtml(anime.title)}</h1>
                ${altTitles ? `<div class="anime-alt-title">${escapeHtml(altTitles)}</div>` : ''}
                
                <div class="anime-meta" style="font-size: 1rem; margin-bottom: 15px;">
                    <span class="meta-tag type">${anime.type || 'TV'}</span> • 
                    <span class="meta-tag status">${anime.status || 'Unknown'}</span> • 
                    <span class="meta-tag">${anime.aired || anime.year || ''}</span>
                    ${genresHtml ? '• ' + genresHtml : ''}
                </div>
                
                <div class="anime-stats">
                    <div class="stat">
                        <strong>${anime.total_episodes || 0}</strong> Episodes
                    </div>
                    <div class="stat">
                        <strong>${anime.score || 'N/A'}</strong> MAL Score
                    </div>
                </div>
                
                ${synopsis}
            </div>
        </div>
    `;
}

function renderEpisodes(episodes) {
    const container = document.getElementById('episodes-grid');
    container.className = 'episodes-grid'; // Revert class to match CSS

    container.innerHTML = episodes.map(ep => `
        <div class="episode-card ${ep.filler ? 'filler' : ''}" 
             data-session="${ep.session}" 
             data-episode="${ep.episode}">
            <span class="episode-number">${ep.episode}</span>
            <span class="episode-label">Episode</span>
        </div>
    `).join('');

    // Update range picker max values
    document.getElementById('range-end').max = episodes.length;
    document.getElementById('range-end').value = Math.min(12, episodes.length);
    document.getElementById('range-start').max = episodes.length;

    // Add click handlers
    container.querySelectorAll('.episode-card').forEach(card => {
        card.addEventListener('click', () => toggleEpisodeSelection(card));
    });
}

function toggleEpisodeSelection(card) {
    const session = card.dataset.session;

    if (state.selectedEpisodes.has(session)) {
        state.selectedEpisodes.delete(session);
        card.classList.remove('selected');
        card.style.borderColor = '';
        card.style.backgroundColor = '';
    } else {
        state.selectedEpisodes.add(session);
        card.classList.add('selected');
        card.style.borderColor = '';
        card.style.backgroundColor = '';
    }

    updateSelectionCount();
}

function selectAllEpisodes() {
    document.querySelectorAll('.episode-card').forEach(card => {
        state.selectedEpisodes.add(card.dataset.session);
        card.classList.add('selected');
        card.style.borderColor = '';
        card.style.backgroundColor = '';
    });
    updateSelectionCount();
}

function deselectAllEpisodes() {
    document.querySelectorAll('.episode-card').forEach(card => {
        card.classList.remove('selected');
        card.style.borderColor = '';
        card.style.backgroundColor = '';
    });
    state.selectedEpisodes.clear();
    updateSelectionCount();
}

function selectEpisodeRange(start, end) {
    deselectAllEpisodes();

    document.querySelectorAll('.episode-card').forEach(card => {
        const epNum = parseFloat(card.dataset.episode);
        if (epNum >= start && epNum <= end) {
            state.selectedEpisodes.add(card.dataset.session);
            card.classList.add('selected');
            card.style.borderColor = '';
            card.style.backgroundColor = '';
        }
    });

    updateSelectionCount();
}

function updateSelectionCount() {
    const count = state.selectedEpisodes.size;
    document.getElementById('selected-count').textContent = count;
    document.getElementById('download-btn').disabled = count === 0;
}

function backToSearch() {
    document.getElementById('anime-panel').classList.remove('active');
    document.querySelector('.search-section').style.display = 'block';
    state.selectedAnime = null;
    state.episodes = [];
    state.selectedEpisodes.clear();
}

// ============================================
// Downloads View
// ============================================

async function refreshQueueStatus() {
    try {
        const status = await API.getQueueStatus();
        updateQueueStatus(status);
    } catch (error) {
        console.error('Failed to refresh queue status:', error);
    }
}

function updateQueueStatus(status) {
    if (!status) return;

    // Update stats
    document.getElementById('active-count').textContent = status.active_count || 0;
    document.getElementById('pending-count').textContent = status.pending_count || 0;
    document.getElementById('completed-count').textContent = status.completed_count || 0;
    document.getElementById('failed-count').textContent = status.failed_count || 0;

    // Update badge
    const totalActive = (status.active_count || 0) + (status.pending_count || 0);
    const badge = document.getElementById('download-badge');
    if (totalActive > 0) {
        badge.textContent = totalActive;
        badge.style.display = 'inline-flex';
    } else {
        badge.style.display = 'none';
    }

    // Render download list
    renderDownloadList(status);
}

function updateDownloadProgress(task) {
    // Update in queue status
    const existingItem = document.querySelector(`[data-task-id="${task.id}"]`);
    if (existingItem) {
        updateDownloadItem(existingItem, task);
    } else {
        // Refresh the whole list
        refreshQueueStatus();
    }

    // Update badge
    refreshQueueStatus();
}

function renderDownloadList(status) {
    const container = document.getElementById('downloads-list');
    const emptyState = document.getElementById('downloads-empty');

    const allItems = [
        ...(status.active || []),
        ...(status.pending || []),
        ...(status.completed || []).slice(-10),
        ...(status.failed || []).slice(-10)
    ];

    if (allItems.length === 0) {
        container.innerHTML = '';
        container.appendChild(emptyState.cloneNode(true));
        return;
    }

    container.innerHTML = allItems.map(task => `
        <div class="download-item" data-task-id="${task.id}">
            <div class="download-icon ${getStatusClass(task.status)}">
                ${getStatusIcon(task.status)}
            </div>
            <div class="download-info">
                <div class="download-name">${escapeHtml(task.filename)}</div>
                <div class="download-details">
                    <span>${escapeHtml(task.anime_title)}</span>
                    <span>EP ${task.episode}</span>
                    <span>${task.resolution}p</span>
                    ${task.speed > 0 ? `<span>${formatSpeed(task.speed)}</span>` : ''}
                </div>
            </div>
            <div class="download-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${task.progress}%"></div>
                </div>
                <div class="progress-text">
                    ${task.status === 'completed' ? 'Complete' :
            task.status === 'failed' ? 'Failed' :
                task.status === 'stopped' ? 'Stopped' :
                    task.status === 'stopping' ? 'Stopping...' :
                        task.status === 'pending' ? 'Pending' :
                            `${task.progress.toFixed(1)}%`}
                </div>
            </div>
            <div class="download-actions">
                ${task.status === 'downloading' || task.status === 'pending' ? `
                    <button class="stop" onclick="stopDownload('${task.id}')" title="Stop">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="6" y="6" width="12" height="12" rx="2"/>
                        </svg>
                    </button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function updateDownloadItem(element, task) {
    const progressFill = element.querySelector('.progress-fill');
    const progressText = element.querySelector('.progress-text');
    const icon = element.querySelector('.download-icon');

    if (progressFill) {
        progressFill.style.width = `${task.progress}%`;
    }

    if (progressText) {
        progressText.textContent = task.status === 'completed' ? 'Complete' :
            task.status === 'failed' ? 'Failed' :
                task.status === 'pending' ? 'Pending' :
                    `${task.progress.toFixed(1)}%`;
    }

    if (icon) {
        icon.className = `download-icon ${getStatusClass(task.status)}`;
        icon.innerHTML = getStatusIcon(task.status);
    }
}

function getStatusClass(status) {
    switch (status) {
        case 'downloading': return 'downloading';
        case 'completed': return 'completed';
        case 'failed':
        case 'stopped':
        case 'stopping': return 'stopped';
        default: return '';
    }
}

function getStatusIcon(status) {
    switch (status) {
        case 'downloading':
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7,10 12,15 17,10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>`;
        case 'completed':
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>`;
        case 'failed':
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>`;
        default:
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <polyline points="12 6 12 12 16 14"/>
            </svg>`;
    }
}

async function stopDownload(taskId) {
    try {
        await API.cancelDownload(taskId);
        showToast('info', 'Stopped', 'Download stopped');
        refreshQueueStatus();
    } catch (error) {
        showToast('error', 'Error', 'Failed to stop download');
    }
}

// ============================================
// Settings
// ============================================

async function loadSettingsUI() {
    try {
        const settings = await API.getSettings();
        state.settings = { ...state.settings, ...settings };

        document.getElementById('download-path').value = settings.download_path || '';
        document.getElementById('max-workers').value = settings.max_workers || 4;
        document.getElementById('workers-value').textContent = settings.max_workers || 4;

        // Load from localStorage for default quality
        const saved = localStorage.getItem('animepahe_settings');
        if (saved) {
            const local = JSON.parse(saved);
            document.getElementById('default-quality').value = local.defaultQuality || 0;
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    try {
        const downloadPath = document.getElementById('download-path').value.trim();
        const maxWorkers = parseInt(document.getElementById('max-workers').value);
        const defaultQuality = parseInt(document.getElementById('default-quality').value);

        // Update server settings
        await API.updateSettings({
            download_path: downloadPath || null,
            max_workers: maxWorkers
        });

        // Save to localStorage
        state.settings = { downloadPath, maxWorkers, defaultQuality };
        saveSettingsToStorage();

        showToast('success', 'Saved', 'Settings saved successfully');
    } catch (error) {
        showToast('error', 'Error', 'Failed to save settings');
    }
}

// ============================================
// Toast Notifications
// ============================================

function showToast(type, title, message, duration = 4000) {
    const container = document.getElementById('toast-container');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-icon">
            ${getToastIcon(type)}
        </div>
        <div class="toast-content">
            <div class="toast-title">${escapeHtml(title)}</div>
            <div class="toast-message">${escapeHtml(message)}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
        </button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

function getToastIcon(type) {
    switch (type) {
        case 'success':
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>`;
        case 'error':
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>`;
        case 'warning':
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>`;
        default:
            return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>`;
    }
}

// ============================================
// Utility Functions
// ============================================

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatSpeed(bytesPerSecond) {
    if (bytesPerSecond < 1024) return `${bytesPerSecond.toFixed(0)} B/s`;
    if (bytesPerSecond < 1024 * 1024) return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`;
    return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ============================================
// Event Listeners
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Load settings
    loadSettings();

    // Connect WebSocket
    connectWebSocket();

    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => switchView(btn.dataset.view));
    });

    // Search
    const searchInput = document.getElementById('search-input');
    const debouncedSearch = debounce(async (query) => {
        if (query.length < 2) {
            document.getElementById('search-results').classList.remove('active');
            return;
        }

        showSearchLoader(true);
        try {
            const data = await API.search(query);
            state.searchResults = data.results;
            renderSearchResults(data.results);
        } catch (error) {
            console.error('Search error:', error);
            showToast('error', 'Search Error', error.message);
        } finally {
            showSearchLoader(false);
        }
    }, 400);

    searchInput.addEventListener('input', (e) => debouncedSearch(e.target.value.trim()));

    // Close search results when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            document.getElementById('search-results').classList.remove('active');
        }
    });

    // Back button
    document.getElementById('back-btn').addEventListener('click', backToSearch);

    // Episode selection buttons
    document.getElementById('select-all-btn').addEventListener('click', selectAllEpisodes);
    document.getElementById('deselect-all-btn').addEventListener('click', deselectAllEpisodes);

    // Range picker
    document.getElementById('select-range-btn').addEventListener('click', () => {
        document.getElementById('range-picker').style.display = 'block';
    });

    document.getElementById('cancel-range-btn').addEventListener('click', () => {
        document.getElementById('range-picker').style.display = 'none';
    });

    document.getElementById('apply-range-btn').addEventListener('click', () => {
        const start = parseInt(document.getElementById('range-start').value);
        const end = parseInt(document.getElementById('range-end').value);
        selectEpisodeRange(start, end);
        document.getElementById('range-picker').style.display = 'none';
    });

    // Download button
    document.getElementById('download-btn').addEventListener('click', async () => {
        if (!state.selectedAnime || state.selectedEpisodes.size === 0) return;

        const quality = parseInt(document.getElementById('quality-select').value);

        try {
            showToast('info', 'Preparing...', 'Getting download links');

            const result = await API.startDownload(
                state.selectedAnime.session,
                state.selectedAnime.title,
                Array.from(state.selectedEpisodes),
                quality
            );

            showToast('success', 'Download Started', `${result.added_count} episodes added to queue`);

            // Switch to downloads view
            switchView('downloads');

        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    // Downloads actions
    document.getElementById('retry-failed-btn').addEventListener('click', async () => {
        try {
            const result = await API.retryFailed();
            showToast('info', 'Retrying', `${result.retried_count} downloads queued for retry`);
            refreshQueueStatus();
        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    document.getElementById('clear-completed-btn').addEventListener('click', async () => {
        try {
            const result = await API.clearCompleted();
            showToast('info', 'Cleared', `${result.cleared_count} completed downloads cleared`);
            refreshQueueStatus();
        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    // Settings
    document.getElementById('max-workers').addEventListener('input', (e) => {
        document.getElementById('workers-value').textContent = e.target.value;
    });

    document.getElementById('save-settings-btn').addEventListener('click', saveSettings);

    // Initial load
    loadSettingsUI();
});

// Make stopDownload globally available for inline onclick
window.stopDownload = stopDownload;
