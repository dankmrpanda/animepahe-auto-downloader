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
    progressBaselineCompleted: null,
    lastQueueAnnouncement: '',
    notificationsPermission: 'default',
    manualImport: {
        episodes: [],
        selectedEpisodes: new Set()
    },
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
        if (ui.currentView && ['search', 'manual', 'downloads', 'settings', 'diagnostics'].includes(ui.currentView)) {
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
        // Read the body exactly once. Calling res.json() and then res.text()
        // throws "body stream already read", so grab the raw text first and
        // attempt to parse it as JSON afterwards.
        let text = '';
        try {
            text = await res.text();
        } catch {
            return fallback;
        }
        if (!text || !text.trim()) return fallback;
        try {
            const payload = JSON.parse(text);
            if (typeof payload === 'string' && payload.trim()) return payload;
            if (payload?.detail) {
                if (typeof payload.detail === 'string') return payload.detail;
                return JSON.stringify(payload.detail);
            }
            if (payload?.error && typeof payload.error === 'string') return payload.error;
        } catch {
            // Not JSON; fall through and return the raw text below.
        }
        return text;
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
            const res = await fetch(`this.baseUrl{path}`);
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
            `/anime/session/episodes?allpages={allPages}`,
            {
                ttlMs: 600000,
                cacheKey: `/anime/session/episodes?allpages={allPages}`,
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

    async startManualImportDownload(animeSession, animeTitle, episodes, resolution) {
        const res = await fetch(`${this.baseUrl}/download/manual-import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                anime_session: animeSession,
                anime_title: animeTitle,
                episodes: episodes,
                resolution: resolution
            })
        });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to start manual import download'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async getQueueStatus({ force = false } = {}) {
        if (force) {
            this._invalidateByPrefix('GET:/queue');
            return this._cachedGet(
                `/queue?_=${Date.now()}`,
                {
                    ttlMs: 0,
                    cacheKey: `/queue:force:${Date.now()}`,
                    errorMessage: 'Failed to get queue status'
                }
            );
        }

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
        const res = await fetch(`this.baseUrl/queue/{taskId}/retry`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to retry task'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async reResolveTask(taskId) {
        const res = await fetch(`this.baseUrl/queue/{taskId}/re-resolve`, { method: 'POST' });
        if (!res.ok) throw new Error(await this._readErrorMessage(res, 'Failed to re-resolve link'));
        this._invalidateByPrefix('GET:/queue');
        return res.json();
    },

    async revalidateTask(taskId) {
        const res = await fetch(`this.baseUrl/queue/{taskId}/revalidate`, { method: 'POST' });
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
        const res = await fetch(`this.baseUrl/queue/{taskId}`, { method: 'DELETE' });
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
    const wsUrl = `protocol//{window.location.host}/api/ws/progress`;

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
            p.textContent = `Preparing download queue: processed/{total}...`;
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
    showToast('error', 'Queue Error', `${reasonLabel}Failed to prepare downloads for ${animeTitle}: ${errorText}`);
    announceStatus(`Download queue preparation failed for ${animeTitle}.`, true);
}

function handleSettingsBroadcast(settings) {
    if (!settings) return;
    // Merge only the fields present in the broadcast so a payload that omits a
    // field (e.g. default_resolution) cannot reset the user's stored preference.
    const incoming = {};
    if (settings.download_path !== undefined || settings.downloadPath !== undefined) {
        incoming.downloadPath = settings.download_path ?? settings.downloadPath ?? '';
    }
    if (settings.max_workers !== undefined || settings.maxWorkers !== undefined) {
        incoming.maxWorkers = Number(settings.max_workers ?? settings.maxWorkers ?? 4);
    }
    if (settings.default_resolution !== undefined || settings.defaultQuality !== undefined) {
        incoming.defaultQuality = Number(settings.default_resolution ?? settings.defaultQuality ?? 0);
    }
    state.settings = { ...state.settings, ...incoming };
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
        <div class="search-result-item" data-session="anime.session"data-title="{escapeHtml(anime.title)}" data-poster="${escapeHtml(anime.poster || '')}">
            <img class="result-poster" src="anime.poster||''"alt="{escapeHtml(anime.title)}" loading="lazy"
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
        <img class="anime-poster" src="anime.poster||''"alt="{escapeHtml(anime.title)}" loading="lazy"
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
            aria-label="Episode ep.episode{ep.filler ? ', filler' : ''}">
            <span class="episode-number">${ep.episode}</span>
            <span class="episode-label">Episode</span>
        </button>
    `).join('');

    // Range selection compares against ep.episode numbers (which may not start at
    // 1 or may be sparse), so bound the inputs by the highest episode number
    // rather than the count. Mirrors the manual-import view.
    const maxEpisode = episodes.length ? Math.max(...episodes.map(e => e.episode)) : 1;
    document.getElementById('range-end').max = maxEpisode;
    document.getElementById('range-end').value = Math.min(12, maxEpisode);
    document.getElementById('range-start').max = maxEpisode;

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
    announceStatus(`countepisode{count === 1 ? '' : 's'} selected.`);
}

function backToSearch() {
    document.getElementById('anime-panel').classList.remove('active');
    document.querySelector('.search-section').style.display = 'block';
    state.selectedAnime = null;
    state.episodes = [];
    state.selectedEpisodes.clear();
}

// ============================================
// Manual Import View
// ============================================

function extractAnimeSession(value) {
    const raw = (value || '').trim();
    if (!raw) return '';
    const uuidMatch = raw.match(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/i);
    if (uuidMatch) return uuidMatch[0];
    return raw;
}

function splitJsonDocuments(text) {
    const docs = [];
    let start = -1;
    let depth = 0;
    let quote = '';
    let escaped = false;

    for (let i = 0; i < text.length; i++) {
        const ch = text[i];

        if (quote) {
            if (escaped) {
                escaped = false;
            } else if (ch === '\\') {
                escaped = true;
            } else if (ch === quote) {
                quote = '';
            }
            continue;
        }

        if (ch === '"' || ch === "'") {
            quote = ch;
            continue;
        }

        if (ch === '{' || ch === '[') {
            if (depth === 0) start = i;
            depth += 1;
        } else if (ch === '}' || ch === ']') {
            depth -= 1;
            if (depth === 0 && start >= 0) {
                docs.push(text.slice(start, i + 1));
                start = -1;
            }
        }
    }

    return docs;
}

function decodeConsoleStringLiteral(text) {
    const trimmed = text.trim();
    if (trimmed.length < 2) return trimmed;

    const quote = trimmed[0];
    if ((quote !== "'" && quote !== '"') || trimmed[trimmed.length - 1] !== quote) {
        return trimmed;
    }

    let decoded = '';
    for (let i = 1; i < trimmed.length - 1; i++) {
        const ch = trimmed[i];
        if (ch !== '\\') {
            decoded += ch;
            continue;
        }

        i += 1;
        const escaped = trimmed[i];
        if (escaped === 'n') decoded += '\n';
        else if (escaped === 'r') decoded += '\r';
        else if (escaped === 't') decoded += '\t';
        else if (escaped === 'b') decoded += '\b';
        else if (escaped === 'f') decoded += '\f';
        else if (escaped === 'u' && i + 4 < trimmed.length - 1) {
            const hex = trimmed.slice(i + 1, i + 5);
            if (/^[0-9a-fA-F]{4}$/.test(hex)) {
                decoded += String.fromCharCode(parseInt(hex, 16));
                i += 4;
            } else {
                decoded += `\\u${hex}`;
                i += 4;
            }
        } else {
            decoded += escaped || '';
        }
    }

    return decoded.trim();
}

function parseJsonPayloadsFromText(text, emptyMessage) {
    const normalized = decodeConsoleStringLiteral((text || '').trim());
    if (!normalized) throw new Error(emptyMessage);

    try {
        return [JSON.parse(normalized)];
    } catch {
        const docs = splitJsonDocuments(normalized);
        if (docs.length === 0) throw new Error('Could not find valid JSON objects in the pasted text');
        return docs.map(doc => JSON.parse(doc));
    }
}

function getReleaseItems(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.data)) return payload.data;
    if (Array.isArray(payload?.episodes)) return payload.episodes;
    if (Array.isArray(payload?.releases)) return payload.releases;
    return [];
}

function normalizeImportedEpisode(item) {
    const episode = Number(item?.episode ?? item?.episode2 ?? item?.number);
    const session = String(item?.session || '').trim();
    if (!Number.isFinite(episode) || !session) return null;
    const rawOptions = item?.options || item?.download_options || item?.downloadOptions || [];
    const options = Array.isArray(rawOptions)
        ? rawOptions.map(normalizeImportedOption).filter(Boolean)
        : [];

    return {
        episode,
        session,
        title: String(item?.title || ''),
        snapshot: String(item?.snapshot || ''),
        duration: String(item?.duration || ''),
        created_at: String(item?.created_at || item?.createdAt || ''),
        filler: item?.filler === true || item?.filler === 1 || item?.filler === '1',
        options
    };
}

function normalizeImportedOption(item) {
    const paheLink = String(item?.pahe_link || item?.paheLink || item?.url || item?.href || '').trim();
    if (!paheLink) return null;
    const quality = String(item?.quality || item?.text || item?.label || '');
    const resMatch = quality.match(/\b(\d{3,4})p\b/i);
    const audioMatch = quality.match(/\b(jpn|eng|multi)\b/i);
    const sizeMatch = quality.match(/(\d+(?:\.\d+)?\s*(?:MB|GB))/i);
    return {
        pahe_link: paheLink,
        quality,
        resolution: Number(item?.resolution || item?.res || (resMatch ? resMatch[1] : 0)),
        audio: String(item?.audio || (audioMatch ? audioMatch[1].toLowerCase() : 'jpn')),
        size: String(item?.size || (sizeMatch ? sizeMatch[1] : ''))
    };
}

function parseManualImportJson() {
    const payloads = parseJsonPayloadsFromText(
        document.getElementById('manual-json').value,
        'Paste the enhanced JSON copied by the browser console command'
    );

    const sessionInput = document.getElementById('manual-session');
    const importedSession = payloads.find(payload => payload?.anime_session)?.anime_session;
    if (importedSession && sessionInput && !sessionInput.value.trim()) {
        sessionInput.value = importedSession;
    }

    const bySession = new Map();
    for (const payload of payloads) {
        for (const item of getReleaseItems(payload)) {
            const episode = normalizeImportedEpisode(item);
            if (episode && !bySession.has(episode.session)) {
                bySession.set(episode.session, episode);
            }
        }
    }

    return Array.from(bySession.values()).sort((a, b) => a.episode - b.episode);
}

function getReleasePayloadsForSnippet() {
    return parseJsonPayloadsFromText(
        document.getElementById('manual-release-json').value,
        'Paste the AnimePahe release API JSON before copying the console command'
    );
}

function buildManualBrowserSnippet() {
    const releasePayloads = getReleasePayloadsForSnippet();
    const animeSession = extractAnimeSession(document.getElementById('manual-session').value);
    const releaseLiteral = JSON.stringify(releasePayloads);
    const sessionLiteral = JSON.stringify(animeSession);

    return `(async () => {
  const releasePayloads = ${releaseLiteral};
  const configuredSession = ${sessionLiteral};
  const animeSession = configuredSession || location.pathname.match(/\\/anime\\/([^/?#]+)/)?.[1] || prompt('Anime session UUID');
  const episodes = releasePayloads.flatMap((releaseJson) => releaseJson.data || releaseJson.episodes || releaseJson.releases || []);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const copyText = async (text) => {
    localStorage.setItem('animepahe_manual_import_json', text);
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const box = document.createElement('textarea');
      box.value = text;
      box.style.position = 'fixed';
      box.style.left = '0';
      box.style.top = '0';
      document.body.appendChild(box);
      box.focus();
      box.select();
      const copied = document.execCommand('copy');
      box.remove();
      return copied;
    }
  };
  const fetchWithBackoff = async (url, tries = 4) => {
    for (let attempt = 1; attempt <= tries; attempt++) {
      const response = await fetch(url, { credentials: 'include' });
      if (response.status !== 429) return response;
      const waitSeconds = Number(response.headers.get('retry-after') || 0);
      const waitMs = waitSeconds > 0 ? waitSeconds * 1000 : 5000 * attempt;
      console.warn(\`429 for \${url}; waiting \${Math.round(waitMs / 1000)}s before retry \${attempt}/\${tries}\`);
      await sleep(waitMs);
    }
    return fetch(url, { credentials: 'include' });
  };
  const parseOptions = (html) => [...html.matchAll(/href="(https:\\/\\/pahe\\.win\\/\\S*)"[^>]*>([^)]*\\))[^<]*</g)].map((m) => {
    const quality = m[2] || '';
    const res = quality.match(/\\b(\\d{3,4})p\\b/i);
    const audio = quality.match(/\\b(jpn|eng|multi)\\b/i);
    const size = quality.match(/(\\d+(?:\\.\\d+)?\\s*(?:MB|GB))/i);
    return {
      pahe_link: decodeURIComponent(m[1]),
      quality,
      resolution: res ? Number(res[1]) : 0,
      audio: audio ? audio[1].toLowerCase() : 'jpn',
      size: size ? size[1] : ''
    };
  });
  const out = [];
  for (const ep of episodes) {
    const response = await fetchWithBackoff(\`/play/\${animeSession}/\${ep.session}\`);
    if (!response.ok) {
      console.warn(\`Skipping episode \${ep.episode}: HTTP \${response.status}\`);
      out.push({ ...ep, options: [], play_status: response.status });
      await sleep(2500);
      continue;
    }
    const html = await response.text();
    out.push({ ...ep, options: parseOptions(html) });
    console.log(\`Parsed episode \${ep.episode}: \${out[out.length - 1].options.length} options\`);
    await sleep(2500);
  }
  const result = JSON.stringify({ anime_session: animeSession, data: out }, null, 2);
  const copied = await copyText(result);
  console.log(copied
    ? \`Copied \${out.length} episodes with play-page options.\`
    : 'Could not auto-copy. Backup saved as localStorage.animepahe_manual_import_json.');
})();`;
}

function updateManualBrowserSnippet() {
    const snippetBox = document.getElementById('manual-browser-snippet');
    if (!snippetBox) return;
    try {
        snippetBox.value = buildManualBrowserSnippet();
    } catch (error) {
        snippetBox.value = `// ${error.message}`;
    }
}

function renderManualImportEpisodes() {
    const container = document.getElementById('manual-episodes-grid');
    const summary = document.getElementById('manual-import-summary');
    const episodes = state.manualImport.episodes;

    if (!episodes.length) {
        container.innerHTML = '';
        summary.textContent = 'No imported episodes';
        updateManualImportSelectionCount();
        return;
    }

    const first = episodes[0]?.episode;
    const last = episodes[episodes.length - 1]?.episode;
    const optionCount = episodes.reduce((total, ep) => total + (ep.options?.length || 0), 0);
    summary.textContent = `${episodes.length} imported episodes (${first} to ${last})${optionCount ? ` with ${optionCount} play-page options` : ''}`;

    container.innerHTML = episodes.map(ep => `
        <button
            type="button"
            class="manual-episode-card ${ep.filler ? 'filler' : ''}"
            data-session="${escapeHtml(ep.session)}"
            data-episode="${ep.episode}"
            aria-pressed="false"
            title="${escapeHtml(ep.title || `Episode ${ep.episode}`)}">
            <span class="episode-number">${ep.episode}</span>
            <span class="episode-label">Episode</span>
        </button>
    `).join('');

    container.querySelectorAll('.manual-episode-card').forEach(card => {
        card.addEventListener('click', () => toggleManualImportEpisode(card));
    });

    document.getElementById('manual-range-start').max = Math.max(last || 1, 1);
    document.getElementById('manual-range-end').max = Math.max(last || 1, 1);
    document.getElementById('manual-range-start').value = first || 1;
    document.getElementById('manual-range-end').value = Math.min((first || 1) + 11, last || 12);
    document.getElementById('manual-select-all-btn').disabled = false;
    document.getElementById('manual-select-range-btn').disabled = false;
    updateManualImportSelectionCount();
}

function toggleManualImportEpisode(card) {
    const session = card.dataset.session;
    if (state.manualImport.selectedEpisodes.has(session)) {
        state.manualImport.selectedEpisodes.delete(session);
        card.classList.remove('selected');
        card.setAttribute('aria-pressed', 'false');
    } else {
        state.manualImport.selectedEpisodes.add(session);
        card.classList.add('selected');
        card.setAttribute('aria-pressed', 'true');
    }
    updateManualImportSelectionCount();
}

function selectAllManualImportEpisodes() {
    document.querySelectorAll('.manual-episode-card').forEach(card => {
        state.manualImport.selectedEpisodes.add(card.dataset.session);
        card.classList.add('selected');
        card.setAttribute('aria-pressed', 'true');
    });
    updateManualImportSelectionCount();
}

function deselectManualImportEpisodes() {
    document.querySelectorAll('.manual-episode-card').forEach(card => {
        card.classList.remove('selected');
        card.setAttribute('aria-pressed', 'false');
    });
    state.manualImport.selectedEpisodes.clear();
    updateManualImportSelectionCount();
}

function selectManualImportRange(start, end) {
    if (start > end) {
        [start, end] = [end, start];
    }
    deselectManualImportEpisodes();
    document.querySelectorAll('.manual-episode-card').forEach(card => {
        const epNum = parseFloat(card.dataset.episode);
        if (epNum >= start && epNum <= end) {
            state.manualImport.selectedEpisodes.add(card.dataset.session);
            card.classList.add('selected');
            card.setAttribute('aria-pressed', 'true');
        }
    });
    updateManualImportSelectionCount();
}

function updateManualImportSelectionCount() {
    const count = state.manualImport.selectedEpisodes.size;
    const hasEpisodes = state.manualImport.episodes.length > 0;
    document.getElementById('manual-selected-count').textContent = count;
    document.getElementById('manual-download-btn').disabled = count === 0;
    document.getElementById('manual-select-all-btn').disabled = !hasEpisodes;
    document.getElementById('manual-select-range-btn').disabled = !hasEpisodes;
}

function clearManualImport() {
    state.manualImport.episodes = [];
    state.manualImport.selectedEpisodes.clear();
    document.getElementById('manual-release-json').value = '';
    document.getElementById('manual-json').value = '';
    document.getElementById('manual-range-picker').style.display = 'none';
    updateManualBrowserSnippet();
    renderManualImportEpisodes();
}

function parseManualImport() {
    try {
        const episodes = parseManualImportJson();
        if (episodes.length === 0) {
            throw new Error('No episodes with session IDs were found in the pasted JSON');
        }
        const optionCount = episodes.reduce((total, episode) => total + (episode.options?.length || 0), 0);
        if (optionCount === 0) {
            throw new Error('This looks like release API JSON only. Run the generated console command and paste its enhanced JSON output here.');
        }
        state.manualImport.episodes = episodes;
        state.manualImport.selectedEpisodes.clear();
        renderManualImportEpisodes();
        showToast('success', 'Episodes Imported', `${episodes.length} episodes and ${optionCount} options ready`);
        announceStatus(`${episodes.length} imported episodes ready.`);
    } catch (error) {
        showToast('error', 'Import Failed', error.message);
        announceStatus('Manual import failed.', true);
    }
}

async function copyManualBrowserSnippet() {
    try {
        const snippet = buildManualBrowserSnippet();
        document.getElementById('manual-browser-snippet').value = snippet;
        await navigator.clipboard.writeText(snippet);
        showToast('success', 'Snippet Copied', 'Run it in the AnimePahe page console');
    } catch (error) {
        updateManualBrowserSnippet();
        document.getElementById('manual-browser-snippet').select();
        showToast('error', 'Snippet Not Ready', error.message);
    }
}

async function downloadManualImportSelection() {
    const animeTitle = document.getElementById('manual-title').value.trim();
    const animeSession = extractAnimeSession(document.getElementById('manual-session').value);
    const resolution = parseInt(document.getElementById('manual-quality').value, 10);

    if (!animeTitle) {
        showToast('error', 'Missing Title', 'Enter the anime title');
        return;
    }
    if (!animeSession) {
        showToast('error', 'Missing Session', 'Enter the AnimePahe anime URL or session UUID');
        return;
    }

    const selected = state.manualImport.episodes.filter(ep => state.manualImport.selectedEpisodes.has(ep.session));
    if (selected.length === 0) {
        showToast('error', 'No Episodes', 'Select at least one imported episode');
        return;
    }
    const missingOptions = selected.filter(ep => !ep.options || ep.options.length === 0);
    if (missingOptions.length > 0) {
        showToast('error', 'Missing Options', `Episode ${missingOptions[0].episode} has no pahe.win options`);
        return;
    }

    try {
        state.processingDownloads = true;
        showToast('info', 'Preparing...', 'Resolving imported episodes');
        const result = await API.startManualImportDownload(animeSession, animeTitle, selected, resolution);
        showToast('success', 'Manual Download Started', result.message || 'Imported episodes are processing');
        announceStatus('Manual import downloads queued successfully.');
        switchView('downloads');
    } catch (error) {
        state.processingDownloads = false;
        showToast('error', 'Manual Download Failed', error.message);
    }
}

// ============================================
// Downloads View
// ============================================

async function refreshQueueStatus(options = {}) {
    try {
        const status = await API.getQueueStatus(options);
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
        // Queue is idle: drop the baseline so the next batch starts from ~0%.
        state.progressBaselineCompleted = null;
        return;
    }

    container.style.display = 'flex';

    // status.completed_count is the LIFETIME completed history (capped at 200),
    // so it must not be used directly as the denominator. Capture a baseline at
    // the moment a new batch begins and only count completions since then, so a
    // fresh batch reads ~0% and climbs toward 100% as its tasks finish.
    const lifetimeCompleted = status.completed_count || 0;
    if (state.progressBaselineCompleted === null || state.progressBaselineCompleted > lifetimeCompleted) {
        state.progressBaselineCompleted = lifetimeCompleted;
    }
    const sessionCompleted = Math.max(0, lifetimeCompleted - state.progressBaselineCompleted);

    // Calculate overall progress from the current queue only: active + pending
    // (pending counts as 0%) plus the completed tasks from this session.
    const inFlight = [...(status.active || []), ...(status.pending || [])];
    const totalTasks = activeCount + sessionCompleted;

    let progressSum = sessionCompleted * 100;
    for (const task of inFlight) {
        progressSum += Math.max(0, Math.min(100, Number(task.progress) || 0));
    }
    const overallPercent = totalTasks > 0 ? (progressSum / totalTasks) : 0;
    const clampedPercent = Math.max(0, Math.min(100, overallPercent));

    fill.style.width = `${clampedPercent}%`;
    text.textContent = `${clampedPercent.toFixed(0)}%`;
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

    const isTerminal = ['completed', 'failed', 'stopped'].includes(task.status);
    if (isTerminal) {
        // Prevent state.speedHistory from growing without bound.
        delete state.speedHistory[task.id];
    }
    refreshQueueStatus({ force: isTerminal });
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
    const progress = Math.max(0, Math.min(100, Number(task.progress) || 0));
    return `${progress.toFixed(1)}%`;
}

function getFailureSummary(task) {
    const reason = task.failure_reason ? getFailureLabel(task.failure_reason) : '';
    const detail = task.failure_detail || task.error || '';
    if (!reason && !detail) return '';
    if (!reason) return detail;
    if (!detail) return reason;
    return `${reason}: ${detail}`;
}

// Markup for the downloads "empty state". Kept as a module-level constant so it
// can always be re-rendered: the original #downloads-empty node is nested inside
// #downloads-list and gets destroyed the first time the queue list is populated.
const EMPTY_DOWNLOADS_HTML = `
    <div class="empty-state" id="downloads-empty">
        <div class="empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7,10 12,15 17,10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
        </div>
        <h3>No Downloads</h3>
        <p>Search for an anime and add episodes to start downloading</p>
    </div>
`;

function renderDownloadList(status) {
    const container = document.getElementById('downloads-list');

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
        // #downloads-empty lives INSIDE #downloads-list, so a populated render
        // (container.innerHTML = ...) destroys it. Rebuild the empty state from
        // a module-level template instead of cloning a node that may be gone.
        if (state.processingDownloads) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon" style="animation: spin 1s linear infinite;">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                        </svg>
                    </div>
                    <h3>Processing Downloads</h3>
                    <p>Preparing download queue...</p>
                </div>
            `;
        } else {
            container.innerHTML = EMPTY_DOWNLOADS_HTML;
        }
        return;
    }

    container.innerHTML = allItems.map(task => {
        const smoothSpeed = task.speed > 0 ? getSmoothedSpeed(task.id, task.speed) : 0;
        const isIndeterminate = task.status === 'downloading' && task.total_bytes === 0;
        const progress = task.status === 'completed'
            ? 100
            : Math.max(0, Math.min(100, Number(task.progress) || 0));
        const retryInfo = task.retry_count > 0 ? ` (retry ${task.retry_count})` : '';
        const failureSummary = getFailureSummary(task);

        return `
        <div class="download-item" data-task-id="${task.id}">
            <div class="download-icon ${getStatusClass(task.status)}">
                ${getStatusIcon(task.status)}
            </div>
            <div class="download-info">
                <div class="download-name">escapeHtml(task.filename){retryInfo}</div>
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
                    <div class="progress-fill${isIndeterminate ? ' indeterminate' : ''}" style="width: ${isIndeterminate ? '30' : progress}%"></div>
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
        const progress = task.status === 'completed'
            ? 100
            : Math.max(0, Math.min(100, Number(task.progress) || 0));
        progressFill.classList.toggle('indeterminate', isIndeterminate);
        if (!isIndeterminate) {
            progressFill.style.width = `${progress}%`;
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

function renderClearance(clearance) {
    const body = document.getElementById('diag-clearance-body');
    if (!body) return;

    if (!clearance || Object.keys(clearance).length === 0) {
        body.innerHTML = '<p class="hint">No clearance information available</p>';
        return;
    }

    const yesNo = (value) => (value ? 'Yes' : 'No');
    const mode = escapeHtml(String(clearance.clearance_mode ?? 'unknown'));
    const baseUrl = escapeHtml(String(clearance.base_url ?? '-'));
    const animeRows = escapeHtml(String(clearance.animepahe_cookie_rows ?? 0));
    const animeCf = yesNo(clearance.animepahe_has_cf_clearance);
    const kwikRows = escapeHtml(String(clearance.kwik_cookie_rows ?? 0));
    const kwikSession = yesNo(clearance.kwik_has_kwik_session);

    let html = `
        <p>Mode: <strong>${mode}</strong></p>
        <p>Base URL: <strong>${baseUrl}</strong></p>
        <p>AnimePahe cookies: <strong>${animeRows}</strong> rows (cf_clearance: ${animeCf})</p>
        <p>Kwik cookies: <strong>${kwikRows}</strong> rows (kwik_session: ${kwikSession})</p>
    `;

    const hosts = clearance.hosts && typeof clearance.hosts === 'object' ? clearance.hosts : null;
    const hostEntries = hosts ? Object.entries(hosts) : [];
    if (hostEntries.length > 0) {
        html += '<ul class="diag-list">';
        for (const [host, info] of hostEntries) {
            const fresh = info?.clearance_fresh ? 'fresh' : 'stale';
            const cls = info?.clearance_fresh ? 'ok' : 'fail';
            const age = Number.isFinite(info?.age_seconds)
                ? `${Math.round(info.age_seconds)}s ago`
                : 'never minted';
            html += `
                <li class="${cls}">
                    <strong>${escapeHtml(host)}</strong><br>
                    clearance: ${yesNo(info?.has_clearance)}, escapeHtml(fresh)({escapeHtml(age)})
                </li>
            `;
        }
        html += '</ul>';
    }

    body.innerHTML = html;
}

function renderDiagnostics(data) {
    const health = data?.health || {};
    const metrics = data?.metrics || {};

    const healthStatus = document.getElementById('diag-health-status');
    const healthUpdated = document.getElementById('diag-health-updated');
    const animepaheBase = document.getElementById('diag-animepahe-base');
    const curlImpersonate = document.getElementById('diag-curl-impersonate');
    if (healthStatus) healthStatus.textContent = (health.status || 'unknown').toUpperCase();
    if (healthUpdated) healthUpdated.textContent = formatDiagTime(data?.generated_at || health.checked_at);
    if (animepaheBase) animepaheBase.textContent = health.animepahe_base_url || data?.environment_checks?.animepahe_base_url || '-';
    if (curlImpersonate) curlImpersonate.textContent = health.curl_impersonate || data?.environment_checks?.curl_impersonate || '-';

    document.getElementById('metric-started').textContent = metrics.downloads_started ?? 0;
    document.getElementById('metric-completed').textContent = metrics.downloads_completed ?? 0;
    document.getElementById('metric-failed').textContent = metrics.downloads_failed ?? 0;
    document.getElementById('metric-retried').textContent = metrics.downloads_retried ?? 0;

    renderClearance(data?.clearance);
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
        const manualQuality = document.getElementById('manual-quality');
        if (manualQuality) {
            manualQuality.value = String(state.settings.defaultQuality);
        }

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

    // Manual import
    document.getElementById('manual-release-json').addEventListener('input', updateManualBrowserSnippet);
    document.getElementById('manual-session').addEventListener('input', updateManualBrowserSnippet);
    document.getElementById('manual-parse-btn').addEventListener('click', parseManualImport);
    document.getElementById('manual-copy-snippet-btn').addEventListener('click', copyManualBrowserSnippet);
    document.getElementById('manual-select-all-btn').addEventListener('click', selectAllManualImportEpisodes);
    document.getElementById('manual-select-range-btn').addEventListener('click', () => {
        document.getElementById('manual-range-picker').style.display = 'block';
    });
    document.getElementById('manual-clear-btn').addEventListener('click', clearManualImport);
    document.getElementById('manual-cancel-range-btn').addEventListener('click', () => {
        document.getElementById('manual-range-picker').style.display = 'none';
    });
    document.getElementById('manual-apply-range-btn').addEventListener('click', () => {
        const start = parseFloat(document.getElementById('manual-range-start').value);
        const end = parseFloat(document.getElementById('manual-range-end').value);
        selectManualImportRange(start, end);
        document.getElementById('manual-range-picker').style.display = 'none';
    });
    document.getElementById('manual-download-btn').addEventListener('click', downloadManualImportSelection);

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
            showToast('info', 'Preparing...', 'Preparing download queue');
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
            announceStatus(`result.retriedcountdownload{result.retried_count === 1 ? '' : 's'} queued for retry.`);
            refreshQueueStatus();
        } catch (error) {
            showToast('error', 'Error', error.message);
        }
    });

    document.getElementById('stop-all-btn').addEventListener('click', async () => {
        if (!confirm('Are you sure you want to stop all downloads?')) return;
        try {
            const result = await API.cancelAllDownloads();
            state.speedHistory = {};
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
            state.speedHistory = {};
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
    updateManualBrowserSnippet();
    switchView(state.currentView);
});

// Make functions globally available for inline onclick
window.stopDownload = stopDownload;
window.retryTask = retryTask;
window.reResolveTask = reResolveTask;
window.revalidateTask = revalidateTask;
window.clearSearchHistory = clearSearchHistory;
window.performSearch = performSearch;


