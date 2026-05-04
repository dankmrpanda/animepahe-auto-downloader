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
    wsReconnectAttempts: 0,
    wsPingInterval: null,
    processingDownloads: false,
    queuePaused: false,
    qualitySelectOverride: null,
    searchHighlightIndex: -1,
    speedHistory: {},
    lastActiveAndPending: 0,
    lastQueueAnnouncement: '',
    notificationsPermission: 'default',
};

const STORAGE_KEYS = {
    settings: 'animepahe_settings',
    uiState: 'animepahe_ui_state',
    searchHistory: 'animepahe_search_history'
};

const FAILURE_REASON_LABELS = {
    network: 'Network',
    link_expired: 'Link Expired',
    integrity_failed: 'Integrity Failed',
    disk_full: 'Disk Full',
    cancelled: 'Cancelled',
    paused: 'Paused',
    file_conflict: 'File In Use',
    path_error: 'Path Error',
    unknown: 'Unknown'
};

function normalizeSettingsPayload(payload = {}) {
    return {
        downloadPath: payload.download_path ?? payload.downloadPath ?? '',
        maxWorkers: Number(payload.max_workers ?? payload.maxWorkers ?? 4),
        defaultQuality: Number(payload.default_resolution ?? payload.defaultQuality ?? 0)
    };
}

function getFailureLabel(reason) {
    return FAILURE_REASON_LABELS[reason] || 'Unknown';
}

// Load settings from localStorage
function loadSettings() {
    const saved = localStorage.getItem(STORAGE_KEYS.settings);
    if (saved) {
        try {
            state.settings = { ...state.settings, ...normalizeSettingsPayload(JSON.parse(saved)) };
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    }
}

// Save settings to localStorage
function saveSettingsToStorage() {
    localStorage.setItem(STORAGE_KEYS.settings, JSON.stringify(state.settings));
}

function loadUIState() {
    const saved = localStorage.getItem(STORAGE_KEYS.uiState);
    if (!saved) return;
    try {
        const ui = JSON.parse(saved);
        if (ui.currentView && ['search', 'downloads', 'settings', 'diagnostics'].includes(ui.currentView)) {
            state.currentView = ui.currentView;
        }
        if (Number.isFinite(ui.qualitySelect)) {
            state.qualitySelectOverride = Number(ui.qualitySelect);
        }
    } catch (e) {
        console.error('Failed to load UI state:', e);
    }
}

function saveUIState(partial = {}) {
    let base = {};
    try {
        base = JSON.parse(localStorage.getItem(STORAGE_KEYS.uiState) || '{}');
    } catch {
        base = {};
    }
    const next = {
        ...base,
        currentView: state.currentView,
        qualitySelect: Number.isFinite(partial.qualitySelect)
            ? partial.qualitySelect
            : parseInt(document.getElementById('quality-select')?.value || String(state.settings.defaultQuality), 10),
        ...partial
    };
    localStorage.setItem(STORAGE_KEYS.uiState, JSON.stringify(next));
}

function announceStatus(message, assertive = false) {
    const announcer = document.getElementById('status-announcer');
    if (!announcer || !message) return;
    announcer.setAttribute('aria-live', assertive ? 'assertive' : 'polite');
    announcer.textContent = '';
    window.setTimeout(() => {
        announcer.textContent = message;
    }, 10);
}

// ============================================
// Search History
// ============================================

function getSearchHistory() {
    try {
        return JSON.parse(localStorage.getItem(STORAGE_KEYS.searchHistory) || '[]');
    } catch {
        return [];
    }
}

function addSearchHistory(query) {
    if (!query || query.length < 2) return;
    let history = getSearchHistory().filter(q => q !== query);
    history.unshift(query);
    if (history.length > 10) history = history.slice(0, 10);
    localStorage.setItem(STORAGE_KEYS.searchHistory, JSON.stringify(history));
}

function clearSearchHistory() {
    localStorage.removeItem(STORAGE_KEYS.searchHistory);
}

function renderSearchHistory() {
    const container = document.getElementById('search-results');
    const history = getSearchHistory();
    if (history.length === 0) return;

    container.innerHTML = `
        <div class="search-history-header">
            <span>Recent Searches</span>
            <button onclick="clearSearchHistory(); document.getElementById('search-results').classList.remove('active');">Clear</button>
        </div>
        ${history.map(q => `
            <div class="search-history-item" data-query="${escapeHtml(q)}">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="1,4 1,10 7,10"/>
                    <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                </svg>
                ${escapeHtml(q)}
            </div>
        `).join('')}
    `;
    container.classList.add('active');

    container.querySelectorAll('.search-history-item').forEach(item => {
        item.addEventListener('click', () => {
            const input = document.getElementById('search-input');
            input.value = item.dataset.query;
            container.classList.remove('active');
            performSearch();
        });
    });
}

// ============================================
// API Functions
// ============================================

const API = {
    baseUrl: '/api',
    cache: new Map(),
    inflight: new Map(),

    _clone(value) {
        if (typeof structuredClone === 'function') {
            return structuredClone(value);
        }
        return JSON.parse(JSON.stringify(value));
    },

    _cacheGet(key) {
        const entry = this.cache.get(key);
        if (!entry) return null;
        if (Date.now() >= entry.expiresAt) {
            this.cache.delete(key);
            return null;
        }
        return this._clone(entry.value);
    },

    _cacheSet(key, value, ttlMs) {
        if (ttlMs <= 0) return;
        this.cache.set(key, {
            value: this._clone(value),
            expiresAt: Date.now() + ttlMs
        });
    },

    _invalidateByPrefix(prefixes) {
        const list = Array.isArray(prefixes) ? prefixes : [prefixes];
        for (const key of this.cache.keys()) {
            if (list.some(prefix => key.startsWith(prefix))) {
                this.cache.delete(key);
            }
        }
    },

    async _readErrorMessage(res, fallback) {
        try {
            const payload = await res.json();
            if (typeof payload === 'string' && payload.trim()) return payload;
            if (payload?.detail) {
                if (typeof payload.detail === 'string') return payload.detail;
                return JSON.stringify(payload.detail);
            }
            if (payload?.error && typeof payload.error === 'string') return payload.error;
        } catch {
            // Ignore JSON parse errors and fallback to text/fallback.
        }
        try {
            const text = await res.text();
            if (text && text.trim()) return text;
        } catch {
            // Ignore text parse errors.
        }
        return fallback;
    },

    async _cachedGet(path, { ttlMs = 0, cacheKey = path, errorMessage = 'Request failed', fallbackOnError = null } = {}) {
        const key = `GET:${cacheKey}`;

        if (ttlMs > 0) {
            const cached = this._cacheGet(key);
            if (cached !== null) return cached;
        }

        if (this.inflight.has(key)) {
            return this.inflight.get(key);
        }

        const request = (async () => {
            const res = await fetch(`${this.baseUrl}${path}`);
            if (!res.ok) {
                if (fallbackOnError !== null) {
                    return this._clone(fallbackOnError);
                }
                throw new Error(errorMessage);
            }
            const data = await res.json();
            this._cacheSet(key, data, ttlMs);
            return this._clone(data);
        })().finally(() => {
            this.inflight.delete(key);
        });

        this.inflight.set(key, request);
        return request;
    },

    async search(query) {
        const normalized = query.trim().toLowerCase();
        return this._cachedGet(
            `/search?q=${encodeURIComponent(query)}`,
            {
                ttlMs: 120000,
                cacheKey: `/search?q=${encodeURIComponent(normalized)}`,
                errorMessage: 'Search failed'
            }
        );
    },

    async getMALPosters(titles) {
        const canonicalTitles = [...new Set((titles || []).filter(Boolean))]
            .sort((a, b) => a.localeCompare(b));
        const titlesParam = canonicalTitles.join('|');
        return this._cachedGet(
            `/search/posters?titles=${encodeURIComponent(titlesParam)}`,
            {
                ttlMs: 600000,
                cacheKey: `/search/posters?titles=${encodeURIComponent(titlesParam)}`,
                fallbackOnError: { posters: {} }
            }
        );
    },

    async getAnimeDetails(session) {
        return this._cachedGet(
            `/anime/${session}`,
            {
                ttlMs: 600000,
                cacheKey: `/anime/${session}`,
                errorMessage: 'Failed to get anime details'
            }
        );
    },

    async getEpisodes(session, allPages = true) {
        return this._cachedGet(
            `/anime/${session}/episodes?all_pages=${allPages}`,
            {
                ttlMs: 600000,
                cacheKey: `/anime/${session}/episodes?all_pages=${allPages}`,
                errorMessage: 'Failed to get episodes'
            }
        );
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
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to start download'));
        this._invalidateByPrefix('GET:/queue');
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
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to start batch download'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async getQueueStatus() {
        return this._cachedGet(
            '/queue',
            {
                ttlMs: 400,
                cacheKey: '/queue',
                errorMessage: 'Failed to get queue status'
            }
        );
    },

    async retryFailed() {
        const res = await fetch(`${this.baseUrl}/queue/retry`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to retry downloads'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async retryTask(taskId) {
        const res = await fetch(`${this.baseUrl}/queue/${taskId}/retry`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to retry task'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async reResolveTask(taskId) {
        const res = await fetch(`${this.baseUrl}/queue/${taskId}/re-resolve`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to re-resolve link'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async revalidateTask(taskId) {
        const res = await fetch(`${this.baseUrl}/queue/${taskId}/revalidate`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to validate file'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async clearCompleted() {
        const res = await fetch(`${this.baseUrl}/queue/clear`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to clear completed'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async cancelDownload(taskId) {
        const res = await fetch(`${this.baseUrl}/queue/${taskId}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to cancel download'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async cancelAllDownloads() {
        const res = await fetch(`${this.baseUrl}/queue`, { method: 'DELETE' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to cancel all downloads'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async getSettings() {
        return this._cachedGet(
            '/settings',
            {
                ttlMs: 30000,
                cacheKey: '/settings',
                errorMessage: 'Failed to get settings'
            }
        );
    },

    async updateSettings(settings) {
        const res = await fetch(`${this.baseUrl}/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to update settings'));
        this._invalidateByPrefix('GET:/settings');
        return res.json();
    },

    async pauseQueue() {
        const res = await fetch(`${this.baseUrl}/queue/pause`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to pause queue'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async resumeQueue() {
        const res = await fetch(`${this.baseUrl}/queue/resume`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to resume queue'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async openFolder() {
        const res = await fetch(`${this.baseUrl}/settings/open-folder`);
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to open folder'));
        return res.json();
    },

    async getDiagnostics() {
        return this._cachedGet(
            '/diagnostics',
            {
                ttlMs: 5000,
                cacheKey: '/diagnostics',
                errorMessage: 'Failed to load diagnostics'
            }
        );
    },

    async exportBackup() {
        const res = await fetch(`${this.baseUrl}/backup/export`);
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to export backup'));
        return res.json();
    },

    async importBackup(payload, replaceExisting = true) {
        const res = await fetch(`${this.baseUrl}/backup/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ...payload,
                replace_existing: replaceExisting
            })
        });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to import backup'));
        this._invalidateByPrefix(['GET:/queue', 'GET:/settings', 'GET:/diagnostics']);
        return res.json();
    },

    async runMaintenanceCleanup() {
        const res = await fetch(`${this.baseUrl}/maintenance/cleanup`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to run cleanup'));
        this._invalidateByPrefix(['GET:/queue', 'GET:/diagnostics']);
        return res.json();
    }
};

// ============================================
// WebSocket Connection
// ============================================

function updateConnectionIndicator(status) {
    const indicator = document.getElementById('ws-status');
    if (!indicator) return;
    indicator.className = 'ws-status ' + status;
    const label = status === 'connected' ? 'Connected' :
        status === 'reconnecting' ? 'Reconnecting...' : 'Disconnected';
    indicator.title = label;
    indicator.setAttribute('aria-label', `WebSocket ${label.toLowerCase()}`);
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws/progress`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('WebSocket connected');
        state.wsReconnectAttempts = 0;
        updateConnectionIndicator('connected');

        // Start ping interval (guard against leaks)
        if (!state.wsPingInterval) {
            state.wsPingInterval = setInterval(() => {
                if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                    state.ws.send(JSON.stringify({ type: 'ping' }));
                }
            }, 20000);
        }
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
        updateConnectionIndicator('reconnecting');

        // Clear ping interval
        if (state.wsPingInterval) {
            clearInterval(state.wsPingInterval);
            state.wsPingInterval = null;
        }

        // Reconnect with exponential backoff - never give up
        state.wsReconnectAttempts++;
        const delay = Math.min(30000, 1000 * Math.pow(2, state.wsReconnectAttempts));
        setTimeout(connectWebSocket, delay);
    };

    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

function handleWSMessage(message) {
    switch (message.type) {
        case 'progress':
            updateDownloadProgress(message.task);
            break;
        case 'status':
            updateQueueStatus(message.queue);
            break;
        case 'link_progress':
            updateLinkProgress(message.processed, message.total);
            break;
        case 'link_error':
            handleLinkError(message.error, message.anime_title, message.reason, message.detail);
            break;
        case 'settings':
            handleSettingsBroadcast(message.settings);
            break;
        case 'heartbeat':
        case 'pong':
            break;
        default:
            console.log('Unknown message type:', message.type);
    }
}

function updateLinkProgress(processed, total) {
    if (!state.processingDownloads) return;
    const container = document.getElementById('downloads-list');
    const spinner = container.querySelector('.empty-state');
    if (spinner) {
        const p = spinner.querySelector('p');
        if (p) {
            p.textContent = `Resolving download links: ${processed}/${total}...`;
        }
    }
    if (total > 0 && processed >= total) {
        state.processingDownloads = false;
        refreshQueueStatus();
    }
}

function handleLinkError(error, animeTitle, reason = null, detail = null) {
    state.processingDownloads = false;
    const reasonLabel = reason ? `${getFailureLabel(reason)}: ` : '';
    const errorText = detail || error;
    showToast('error', 'Link Error', `${reasonLabel}Failed to resolve links for ${animeTitle}: ${errorText}`);
    announceStatus(`Download link resolution failed for ${animeTitle}.`, true);
}

function handleSettingsBroadcast(settings) {
    if (!settings) return;
    state.settings = normalizeSettingsPayload(settings);
    saveSettingsToStorage();
    if (state.currentView === 'settings') {
        document.getElementById('max-workers').value = state.settings.maxWorkers;
        document.getElementById('workers-value').textContent = state.settings.maxWorkers;
        document.getElementById('download-path').value = state.settings.downloadPath || '';
        document.getElementById('default-quality').value = state.settings.defaultQuality;
    }
}

// ============================================
// UI Update Functions
// ============================================

function switchView(viewName) {
    state.currentView = viewName;
    saveUIState();

    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === viewName);
    });

    document.querySelectorAll('.view').forEach(view => {
        view.classList.toggle('active', view.id === `${viewName}-view`);
    });

    if (viewName === 'downloads') {
        refreshQueueStatus();
    } else if (viewName === 'settings') {
        loadSettingsUI();
    } else if (viewName === 'diagnostics') {
        refreshDiagnostics();
    }
}

function showSearchLoader(show) {
    document.getElementById('search-loader').classList.toggle('active', show);
}

function renderSearchResults(results) {
    const container = document.getElementById('search-results');
    state.searchHighlightIndex = -1;

    if (!results || results.length === 0) {
        container.innerHTML = '<div class="no-results">No anime found</div>';
        container.classList.add('active');
        return;
    }

    container.innerHTML = results.map(anime => `
        <div class="search-result-item" data-session="${anime.session}" data-title="${escapeHtml(anime.title)}" data-poster="${escapeHtml(anime.poster || '')}">
            <img class="result-poster" src="${anime.poster || ''}" alt="${escapeHtml(anime.title)}" loading="lazy"
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

    // Upgrade posters from MAL in the background
    const titles = results.map(a => a.title).filter(Boolean);
    if (titles.length > 0) {
        API.getMALPosters(titles).then(data => {
            if (!data.posters) return;
            container.querySelectorAll('.search-result-item').forEach(item => {
                const title = item.dataset.title;
                if (data.posters[title]) {
                    const img = item.querySelector('.result-poster');
                    if (img) img.src = data.posters[title];
                    item.dataset.poster = data.posters[title];
                }
            });
        }).catch(() => {});
    }
}

async function selectAnime(session, title, poster) {
    try {
        showToast('info', 'Loading...', 'Fetching anime details');

        document.getElementById('search-results').classList.remove('active');
        document.getElementById('search-input').value = title;

        const [details, episodesData] = await Promise.all([
            API.getAnimeDetails(session),
            API.getEpisodes(session, true)
        ]);

        state.selectedAnime = { session, title, poster, ...details };
        state.episodes = episodesData.episodes;
        state.selectedEpisodes.clear();

        renderAnimeInfo(state.selectedAnime);
        renderEpisodes(state.episodes);

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
    const altTitles = [anime.english_title, anime.japanese_title].filter(t => t && t !== anime.title).join(' \u2022 ');

    container.innerHTML = `
        <img class="anime-poster" src="${anime.poster || ''}" alt="${escapeHtml(anime.title)}" loading="lazy"
                onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 180 260%22%3E%3Crect fill=%22%231a1a25%22 width=%22180%22 height=%22260%22/%3E%3Ctext x=%2290%22 y=%22130%22 text-anchor=%22middle%22 fill=%22%2371717a%22 font-size=%2216%22%3ENo Image%3C/text%3E%3C/svg%3E'">
        <div class="anime-details">
            <h1 class="anime-title" style="font-size: 2rem; white-space: normal;">${escapeHtml(anime.title)}</h1>
            ${altTitles ? `<div class="anime-alt-title">${escapeHtml(altTitles)}</div>` : ''}

            <div class="anime-meta" style="font-size: 1rem; margin-bottom: 15px;">
                <span class="meta-tag type">${anime.type || 'TV'}</span> \u2022
                <span class="meta-tag status">${anime.status || 'Unknown'}</span> \u2022
                <span class="meta-tag">${anime.aired || anime.year || ''}</span>
                ${genresHtml ? '\u2022 ' + genresHtml : ''}
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
    `;
}

function renderEpisodes(episodes) {
    const container = document.getElementById('episodes-grid');
    container.className = 'episodes-grid';

    container.innerHTML = episodes.map(ep => `
        <button
            type="button"
            class="episode-card ${ep.filler ? 'filler' : ''}"
            data-session="${ep.session}"
            data-episode="${ep.episode}"
            aria-pressed="false"
            aria-label="Episode ${ep.episode}${ep.filler ? ', filler' : ''}">
            <span class="episode-number">${ep.episode}</span>
            <span class="episode-label">Episode</span>
        </button>
    `).join('');

    document.getElementById('range-end').max = episodes.length;
    document.getElementById('range-end').value = Math.min(12, episodes.length);
    document.getElementById('range-start').max = episodes.length;

    const cards = Array.from(container.querySelectorAll('.episode-card'));
    cards.forEach((card, index) => {
        card.addEventListener('click', () => toggleEpisodeSelection(card));
        card.addEventListener('keydown', (event) => {
            const columns = Math.max(1, Math.floor(container.clientWidth / 70));
            let nextIndex = index;
            if (event.key === 'ArrowRight') nextIndex = Math.min(cards.length - 1, index + 1);
            if (event.key === 'ArrowLeft') nextIndex = Math.max(0, index - 1);
            if (event.key === 'ArrowDown') nextIndex = Math.min(cards.length - 1, index + columns);
            if (event.key === 'ArrowUp') nextIndex = Math.max(0, index - columns);
            if (nextIndex !== index) {
                event.preventDefault();
                cards[nextIndex].focus();
            }
        });
    });
}

function toggleEpisodeSelection(card) {
    const session = card.dataset.session;

    if (state.selectedEpisodes.has(session)) {
        state.selectedEpisodes.delete(session);
        card.classList.remove('selected');
        card.setAttribute('aria-pressed', 'false');
    } else {
        state.selectedEpisodes.add(session);
        card.classList.add('selected');
        card.setAttribute('aria-pressed', 'true');
    }

    updateSelectionCount();
}

function selectAllEpisodes() {
    document.querySelectorAll('.episode-card').forEach(card => {
        state.selectedEpisodes.add(card.dataset.session);
        card.classList.add('selected');
        card.setAttribute('aria-pressed', 'true');
    });
    updateSelectionCount();
}

function deselectAllEpisodes() {
    document.querySelectorAll('.episode-card').forEach(card => {
        card.classList.remove('selected');
        card.setAttribute('aria-pressed', 'false');
    });
    state.selectedEpisodes.clear();
    updateSelectionCount();
}

function selectEpisodeRange(start, end) {
    // Swap if start > end
    if (start > end) {
        [start, end] = [end, start];
    }

    deselectAllEpisodes();

    document.querySelectorAll('.episode-card').forEach(card => {
        const epNum = parseFloat(card.dataset.episode);
        if (epNum >= start && epNum <= end) {
            state.selectedEpisodes.add(card.dataset.session);
            card.classList.add('selected');
            card.setAttribute('aria-pressed', 'true');
        }
    });

    updateSelectionCount();
}

function updateSelectionCount() {
    const count = state.selectedEpisodes.size;
    document.getElementById('selected-count').textContent = count;
    document.getElementById('download-btn').disabled = count === 0;
    announceStatus(`${count} episode${count === 1 ? '' : 's'} selected.`);
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

    const queueSummary = `${status.active_count || 0} active, ${status.pending_count || 0} pending, ${(status.failed_count || 0)} failed`;
    if (queueSummary !== state.lastQueueAnnouncement) {
        state.lastQueueAnnouncement = queueSummary;
        announceStatus(`Queue update: ${queueSummary}.`);
    }

    // Update badge
    const totalActive = (status.active_count || 0) + (status.pending_count || 0);
    const badge = document.getElementById('download-badge');
    if (totalActive > 0) {
        badge.textContent = totalActive;
        badge.style.display = 'inline-flex';
    } else {
        badge.style.display = 'none';
    }

    // Check for completion notification
    const prevActiveAndPending = state.lastActiveAndPending;
    state.lastActiveAndPending = totalActive;
    if (prevActiveAndPending > 0 && totalActive === 0 && (status.completed_count || 0) > 0) {
        sendCompletionNotification(status.completed_count);
        announceStatus(`All downloads finished. ${status.completed_count} completed.`, true);
    }

    // Update pause/resume button
    state.queuePaused = !!status.paused;
    updatePauseResumeButton();

    // Update total progress bar
    updateTotalProgress(status);

    // Render download list
    renderDownloadList(status);
}

function updateTotalProgress(status) {
    const container = document.getElementById('total-progress-container');
    const fill = document.getElementById('total-progress-fill');
    const text = document.getElementById('total-progress-text');

    const activeCount = (status.active_count || 0) + (status.pending_count || 0);
    if (activeCount === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';

    // Calculate total progress from active tasks
    const allActive = [...(status.active || []), ...(status.pending || [])];
    const totalCompleted = status.completed_count || 0;
    const totalTasks = activeCount + totalCompleted;

    let progressSum = totalCompleted * 100;
    for (const task of allActive) {
        progressSum += (task.progress || 0);
    }
    const overallPercent = totalTasks > 0 ? (progressSum / totalTasks) : 0;

    fill.style.width = `${overallPercent}%`;
    text.textContent = `${overallPercent.toFixed(0)}%`;
}

function updatePauseResumeButton() {
    const btn = document.getElementById('pause-resume-btn');
    if (!btn) return;
    if (state.queuePaused) {
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="5,3 19,12 5,21"/>
            </svg>
            Resume
        `;
    } else {
        btn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="6" y="4" width="4" height="16"/>
                <rect x="14" y="4" width="4" height="16"/>
            </svg>
            Pause
        `;
    }
}

function updateDownloadProgress(task) {
    const existingItem = document.querySelector(`[data-task-id="${task.id}"]`);
    if (existingItem) {
        updateDownloadItem(existingItem, task);
    }

    refreshQueueStatus();
}

function getSmoothedSpeed(taskId, currentSpeed) {
    if (!state.speedHistory[taskId]) {
        state.speedHistory[taskId] = [];
    }
    const history = state.speedHistory[taskId];
    history.push(currentSpeed);
    if (history.length > 5) history.shift();

    const sum = history.reduce((a, b) => a + b, 0);
    return sum / history.length;
}

function getProgressText(task) {
    if (task.status === 'completed') return 'Complete';
    if (task.status === 'failed') return 'Failed';
    if (task.status === 'stopped') return 'Stopped';
    if (task.status === 'stopping') return 'Stopping...';
    if (task.status === 'pending') return 'Pending';
    return `${task.progress.toFixed(1)}%`;
}

function getFailureSummary(task) {
    const reason = task.failure_reason ? getFailureLabel(task.failure_reason) : '';
    const detail = task.failure_detail || task.error || '';
    if (!reason && !detail) return '';
    if (!reason) return detail;
    if (!detail) return reason;
    return `${reason}: ${detail}`;
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

    if (allItems.length > 0) {
        state.processingDownloads = false;
    }

    if (allItems.length === 0) {
        container.innerHTML = '';

        if (state.processingDownloads) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon" style="animation: spin 1s linear infinite;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                        </svg>
                    </div>
                    <h3>Processing Downloads</h3>
                    <p>Fetching download links and preparing queue...</p>
                </div>
            `;
        } else {
            container.appendChild(emptyState.cloneNode(true));
        }
        return;
    }

    container.innerHTML = allItems.map(task => {
        const smoothSpeed = task.speed > 0 ? getSmoothedSpeed(task.id, task.speed) : 0;
        const isIndeterminate = task.status === 'downloading' && task.total_bytes === 0;
        const retryInfo = task.retry_count > 0 ? ` (retry ${task.retry_count})` : '';
        const failureSummary = getFailureSummary(task);

        return `
        <div class="download-item" data-task-id="${task.id}">
            <div class="download-icon ${getStatusClass(task.status)}">
                ${getStatusIcon(task.status)}
            </div>
            <div class="download-info">
                <div class="download-name">${escapeHtml(task.filename)}${retryInfo}</div>
                <div class="download-details">
                    <span>${escapeHtml(task.anime_title)}</span>
                    <span>EP ${task.episode}</span>
                    <span>${task.resolution}p</span>
                    ${smoothSpeed > 0 ? `<span>${formatSpeed(smoothSpeed)}</span>` : ''}
                    ${failureSummary ? `<span class="failure-reason">${escapeHtml(failureSummary)}</span>` : ''}
                </div>
            </div>
            <div class="download-progress">
                <div class="progress-bar">
                    <div class="progress-fill${isIndeterminate ? ' indeterminate' : ''}" style="width: ${isIndeterminate ? '30' : task.progress}%"></div>
                </div>
                <div class="progress-text">
                    ${getProgressText(task)}
                </div>
            </div>
            <div class="download-actions">
                ${task.status === 'downloading' || task.status === 'pending' ? `
                    <button class="stop" onclick="stopDownload('${task.id}')" title="Stop" aria-label="Stop download ${escapeHtml(task.filename)}">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="6" y="6" width="12" height="12" rx="2"/>
                        </svg>
                    </button>
                ` : ''}
                ${(task.status === 'failed' || task.status === 'stopped') ? `
                    <button class="retry" onclick="retryTask('${task.id}')" title="Retry" aria-label="Retry download ${escapeHtml(task.filename)}">
                        Retry
                    </button>
                ` : ''}
                ${(task.failure_reason === 'link_expired' || task.failure_reason === 'network') ? `
                    <button class="recover" onclick="reResolveTask('${task.id}')" title="Re-resolve link" aria-label="Re-resolve link for ${escapeHtml(task.filename)}">
                        Re-resolve
                    </button>
                ` : ''}
                ${(task.status === 'completed' || task.failure_reason === 'integrity_failed') ? `
                    <button class="recover" onclick="revalidateTask('${task.id}')" title="Re-validate file" aria-label="Re-validate file ${escapeHtml(task.filename)}">
                        Validate
                    </button>
                ` : ''}
            </div>
        </div>
        `;
    }).join('');
}

function updateDownloadItem(element, task) {
    const progressFill = element.querySelector('.progress-fill');
    const progressText = element.querySelector('.progress-text');
    const icon = element.querySelector('.download-icon');

    if (progressFill) {
        const isIndeterminate = task.status === 'downloading' && task.total_bytes === 0;
        progressFill.classList.toggle('indeterminate', isIndeterminate);
        if (!isIndeterminate) {
            progressFill.style.width = `${task.progress}%`;
        }
    }

    if (progressText) {
        progressText.textContent = getProgressText(task);
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
        announceStatus('Download stopped.');
        refreshQueueStatus();
    } catch (error) {
        showToast('error', 'Error', 'Failed to stop download');
    }
}

async function retryTask(taskId) {
    try {
        await API.retryTask(taskId);
        showToast('info', 'Retry Queued', 'Download queued for retry');
        announceStatus('Download queued for retry.');
        refreshQueueStatus();
    } catch (error) {
        showToast('error', 'Retry Failed', error.message);
    }
}

async function reResolveTask(taskId) {
    try {
        await API.reResolveTask(taskId);
        showToast('info', 'Link Refreshed', 'Download link re-resolved and queued');
        announceStatus('Download link re-resolved.');
        refreshQueueStatus();
    } catch (error) {
        showToast('error', 'Re-resolve Failed', error.message);
    }
}

async function revalidateTask(taskId) {
    try {
        const result = await API.revalidateTask(taskId);
        if (result.valid) {
            showToast('success', 'Validation Passed', result.message || 'File is valid');
            announceStatus('File validation passed.');
        } else {
            showToast('warning', 'Validation Failed', result.message || 'File integrity check failed');
            announceStatus('File validation failed.', true);
        }
        refreshQueueStatus();
    } catch (error) {
        showToast('error', 'Validation Error', error.message);
    }
}

function formatDiagTime(iso) {
    if (!iso) return '-';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString();
}

function renderEnvironmentChecks(environmentChecks) {
    const list = document.getElementById('diag-environment-checks');
    if (!list) return;

    const checks = environmentChecks?.checks || {};
    const items = Object.entries(checks);
    if (items.length === 0) {
        list.innerHTML = '<li>No environment checks available</li>';
        return;
    }

    list.innerHTML = items.map(([name, value]) => `
        <li class="${value?.ok ? 'ok' : 'fail'}">
            <strong>${escapeHtml(name.replace(/_/g, ' '))}</strong><br>
            ${escapeHtml(value?.detail || 'No details')}
        </li>
    `).join('');
}

function renderRecentErrors(errors) {
    const list = document.getElementById('diag-recent-errors');
    if (!list) return;
    if (!errors || errors.length === 0) {
        list.innerHTML = '<li class="ok">No recent errors</li>';
        return;
    }
    list.innerHTML = errors.map((error) => `
        <li class="fail">
            <strong>${escapeHtml(error.filename || 'Unknown file')}</strong><br>
            ${escapeHtml(error.failure_reason || 'unknown')}: ${escapeHtml(error.failure_detail || error.error || 'No details')}
        </li>
    `).join('');
}

function renderDiagnostics(data) {
    const health = data?.health || {};
    const metrics = data?.metrics || {};

    const healthStatus = document.getElementById('diag-health-status');
    const healthUpdated = document.getElementById('diag-health-updated');
    if (healthStatus) healthStatus.textContent = (health.status || 'unknown').toUpperCase();
    if (healthUpdated) healthUpdated.textContent = formatDiagTime(data?.generated_at || health.checked_at);

    document.getElementById('metric-started').textContent = metrics.downloads_started ?? 0;
    document.getElementById('metric-completed').textContent = metrics.downloads_completed ?? 0;
    document.getElementById('metric-failed').textContent = metrics.downloads_failed ?? 0;
    document.getElementById('metric-retried').textContent = metrics.downloads_retried ?? 0;

    renderEnvironmentChecks(data?.environment_checks);
    renderRecentErrors(data?.recent_errors);
}

async function refreshDiagnostics() {
    try {
        const data = await API.getDiagnostics();
        renderDiagnostics(data);
    } catch (error) {
        showToast('error', 'Diagnostics', error.message);
    }
}

async function exportBackup() {
    try {
        const backup = await API.exportBackup();
        const blob = new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `animepahe-backup-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        showToast('success', 'Backup Exported', 'Settings and history backup downloaded');
    } catch (error) {
        showToast('error', 'Backup Export Failed', error.message);
    }
}

async function importBackupFromFile(file) {
    try {
        const text = await file.text();
        const payload = JSON.parse(text);
        if (!confirm('Import backup and replace current queue/history?')) return;
        await API.importBackup(payload, true);
        showToast('success', 'Backup Imported', 'Backup import completed');
        refreshQueueStatus();
        loadSettingsUI();
        refreshDiagnostics();
    } catch (error) {
        showToast('error', 'Backup Import Failed', error.message);
    }
}

async function runCleanupTool() {
    try {
        if (!confirm('Run cleanup for stale partial files and orphan queue entries?')) return;
        const result = await API.runMaintenanceCleanup();
        showToast(
            'success',
            'Cleanup Complete',
            `Removed ${result.stale_files_removed || 0} stale files and ${result.orphan_queue_entries_removed || 0} orphan entries`
        );
        refreshQueueStatus();
        refreshDiagnostics();
    } catch (error) {
        showToast('error', 'Cleanup Failed', error.message);
    }
}

// ============================================
// Browser Notifications
// ============================================

function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission().then(perm => {
            state.notificationsPermission = perm;
        });
    } else if ('Notification' in window) {
        state.notificationsPermission = Notification.permission;
    }
}

function sendCompletionNotification(completedCount) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Downloads Complete', {
            body: `All ${completedCount} download(s) have finished.`,
            icon: 'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22%2322c55e%22%3E%3Cpath d=%22M22 11.08V12a10 10 0 1 1-5.93-9.14%22/%3E%3Cpolyline points=%2222 4 12 14.01 9 11.01%22/%3E%3C/svg%3E'
        });
    }
}

// ============================================
// Settings
// ============================================

async function loadSettingsUI() {
    try {
        const settings = normalizeSettingsPayload(await API.getSettings());
        state.settings = { ...state.settings, ...settings };
        saveSettingsToStorage();

        document.getElementById('download-path').value = state.settings.downloadPath || '';
        document.getElementById('max-workers').value = state.settings.maxWorkers || 4;
        document.getElementById('workers-value').textContent = state.settings.maxWorkers || 4;
        document.getElementById('default-quality').value = state.settings.defaultQuality;

        const qualitySelect = document.getElementById('quality-select');
        if (qualitySelect) {
            const preferred = Number.isFinite(state.qualitySelectOverride)
                ? state.qualitySelectOverride
                : state.settings.defaultQuality;
            qualitySelect.value = String(preferred);
            saveUIState({ qualitySelect: preferred });
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveSettings() {
    try {
        const downloadPath = document.getElementById('download-path').value.trim();
        const maxWorkers = parseInt(document.getElementById('max-workers').value, 10);
        const defaultQuality = parseInt(document.getElementById('default-quality').value, 10);

        await API.updateSettings({
            download_path: downloadPath || null,
            max_workers: maxWorkers,
            default_resolution: defaultQuality
        });

        state.settings = { downloadPath, maxWorkers, defaultQuality };
        saveSettingsToStorage();
        saveUIState({ qualitySelect: defaultQuality });

        showToast('success', 'Saved', 'Settings saved successfully');
        announceStatus('Settings saved.');
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
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', type === 'error' ? 'assertive' : 'polite');
    toast.innerHTML = `
        <div class="toast-icon">
            ${getToastIcon(type)}
        </div>
        <div class="toast-content">
            <div class="toast-title">${escapeHtml(title)}</div>
            <div class="toast-message">${escapeHtml(message)}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()" aria-label="Dismiss notification">
            <span class="sr-only">Dismiss notification</span>
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
// Search (top-level for reuse)
// ============================================

async function performSearch() {
    const searchInput = document.getElementById('search-input');
    const query = searchInput.value.trim();
    if (query.length < 2) return;

    addSearchHistory(query);
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
}

// ============================================
// Event Listeners
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    loadUIState();
    connectWebSocket();
    requestNotificationPermission();

    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => switchView(btn.dataset.view));
    });

    // Search
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');

    searchBtn.addEventListener('click', performSearch);

    searchInput.addEventListener('keydown', (e) => {
        const container = document.getElementById('search-results');
        const items = container.querySelectorAll('.search-result-item, .search-history-item');

        if (e.key === 'Escape') {
            container.classList.remove('active');
            state.searchHighlightIndex = -1;
            return;
        }

        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            if (!container.classList.contains('active') || items.length === 0) return;

            // Remove old highlight
            items.forEach(i => i.classList.remove('highlighted'));

            if (e.key === 'ArrowDown') {
                state.searchHighlightIndex = Math.min(state.searchHighlightIndex + 1, items.length - 1);
            } else {
                state.searchHighlightIndex = Math.max(state.searchHighlightIndex - 1, 0);
            }

            const highlighted = items[state.searchHighlightIndex];
            highlighted.classList.add('highlighted');
            highlighted.scrollIntoView({ block: 'nearest' });
            return;
        }

        if (e.key === 'Enter') {
            if (state.searchHighlightIndex >= 0 && items.length > 0) {
                e.preventDefault();
                items[state.searchHighlightIndex].click();
                state.searchHighlightIndex = -1;
            } else {
                performSearch();
            }
            return;
        }
    });

    // Show search history on focus when input is empty
    searchInput.addEventListener('focus', () => {
        if (!searchInput.value.trim()) {
            renderSearchHistory();
        }
    });

    // Close search results when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            document.getElementById('search-results').classList.remove('active');
            state.searchHighlightIndex = -1;
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
        const start = parseInt(document.getElementById('range-start').value, 10);
        const end = parseInt(document.getElementById('range-end').value, 10);
        selectEpisodeRange(start, end);
        document.getElementById('range-picker').style.display = 'none';
    });

    // Download button
    document.getElementById('download-btn').addEventListener('click', async () => {
        if (!state.selectedAnime || state.selectedEpisodes.size === 0) return;

        const quality = parseInt(document.getElementById('quality-select').value, 10);

        try {
            showToast('info', 'Preparing...', 'Getting download links');
            state.processingDownloads = true;

            const result = await API.startDownload(
                state.selectedAnime.session,
                state.selectedAnime.title,
                Array.from(state.selectedEpisodes),
                quality
            );

            showToast('success', 'Download Started', `${result.message}`);
            announceStatus('Downloads queued successfully.');
            switchView('downloads');

        } catch (error) {
            state.processingDownloads = false;
            showToast('error', 'Error', error.message);
        }
    });

    // Downloads actions
    document.getElementById('pause-resume-btn').addEventListener('click', async () => {
        try {
            if (state.queuePaused) {
                await API.resumeQueue();
                showToast('info', 'Resumed', 'Download queue resumed');
                announceStatus('Download queue resumed.');
            } else {
                await API.pauseQueue();
                showToast('info', 'Paused', 'Download queue paused');
                announceStatus('Download queue paused.');
            }
            state.queuePaused = !state.queuePaused;
            updatePauseResumeButton();
        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    document.getElementById('retry-failed-btn').addEventListener('click', async () => {
        try {
            const result = await API.retryFailed();
            showToast('info', 'Retrying', `${result.retried_count} downloads queued for retry`);
            announceStatus(`${result.retried_count} download${result.retried_count === 1 ? '' : 's'} queued for retry.`);
            refreshQueueStatus();
        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    document.getElementById('stop-all-btn').addEventListener('click', async () => {
        if (!confirm('Are you sure you want to stop all downloads?')) return;
        try {
            const result = await API.cancelAllDownloads();
            showToast('info', 'Stopped', `${result.cancelled_count} downloads stopped`);
            announceStatus(`${result.cancelled_count} downloads stopped.`);
            refreshQueueStatus();
        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    document.getElementById('clear-completed-btn').addEventListener('click', async () => {
        try {
            const result = await API.clearCompleted();
            showToast('info', 'Cleared', `${result.cleared_count} completed downloads cleared`);
            announceStatus(`${result.cleared_count} completed downloads cleared.`);
            refreshQueueStatus();
        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    // Settings - auto-save with debounce
    const autoSaveSettings = debounce(async () => {
        try {
            const downloadPath = document.getElementById('download-path').value.trim();
            const maxWorkers = parseInt(document.getElementById('max-workers').value, 10);
            const defaultQuality = parseInt(document.getElementById('default-quality').value, 10);

            await API.updateSettings({
                download_path: downloadPath || null,
                max_workers: maxWorkers,
                default_resolution: defaultQuality
            });

            state.settings = { downloadPath, maxWorkers, defaultQuality };
            saveSettingsToStorage();
            saveUIState({ qualitySelect: defaultQuality });

            showToast('success', 'Saved', 'Settings updated', 2000);
            announceStatus('Settings updated.');
        } catch (error) {
            showToast('error', 'Error', 'Failed to save settings');
        }
    }, 800);

    document.getElementById('max-workers').addEventListener('input', (e) => {
        document.getElementById('workers-value').textContent = e.target.value;
        autoSaveSettings();
    });

    document.getElementById('download-path').addEventListener('change', autoSaveSettings);
    document.getElementById('default-quality').addEventListener('change', autoSaveSettings);
    document.getElementById('quality-select').addEventListener('change', (e) => {
        const quality = parseInt(e.target.value, 10);
        state.qualitySelectOverride = quality;
        state.settings.defaultQuality = quality;
        saveSettingsToStorage();
        saveUIState({ qualitySelect: quality });
    });

    document.getElementById('save-settings-btn').addEventListener('click', saveSettings);

    // Open folder button
    document.getElementById('open-folder-btn').addEventListener('click', async () => {
        try {
            await API.openFolder();
        } catch (error) {
            showToast('error', 'Error', 'Failed to open download folder');
        }
    });

    // Diagnostics tools
    document.getElementById('refresh-diagnostics-btn').addEventListener('click', refreshDiagnostics);
    document.getElementById('export-backup-btn').addEventListener('click', exportBackup);
    document.getElementById('run-cleanup-btn').addEventListener('click', runCleanupTool);
    document.getElementById('import-backup-btn').addEventListener('click', () => {
        document.getElementById('import-backup-input').click();
    });
    document.getElementById('import-backup-input').addEventListener('change', async (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) return;
        await importBackupFromFile(file);
        event.target.value = '';
    });

    // Initial load
    loadSettingsUI();
    switchView(state.currentView);
});

// Make functions globally available for inline onclick
window.stopDownload = stopDownload;
window.retryTask = retryTask;
window.reResolveTask = reResolveTask;
window.revalidateTask = revalidateTask;
window.clearSearchHistory = clearSearchHistory;
window.performSearch = performSearch;
