/**
 * Kerala Landslide Risk Monitor - Frontend
 * Clean rebuild
 */

const CONFIG = {
    mapCenter: [10.8505, 76.2711],
    mapZoom: 7,
    apiBase: window.location.origin
};

let map = null;
let markers = {};
let predictions = {};
let pulseMarkers = {};  // Pulsing animation markers for high-risk

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    loadData();
    initWebSocket();
});

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    console.log('Connecting to WebSocket:', wsUrl);

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log('WebSocket connected successfully!');
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'refresh') {
            console.log('Real-time refresh triggered');
            loadData();
        }
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    socket.onclose = () => {
        console.log('WS closed, retrying in 3s...');
        setTimeout(initWebSocket, 3000);
    };
}

function initMap() {
    map = L.map('map', {
        center: CONFIG.mapCenter,
        zoom: CONFIG.mapZoom
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        maxZoom: 19
    }).addTo(map);

    console.log('Map initialized');

    // AGGRESSIVE FIX: Close search results on ANY map interaction or outside click
    const closeSearch = () => {
        const results = document.getElementById('searchResults');
        if (results && !results.classList.contains('hidden')) {
            results.classList.add('hidden');
        }
    };

    // 1. Map interactions
    map.on('click', closeSearch);
    map.on('dragstart', closeSearch);
    map.on('zoomstart', closeSearch);

    // 2. Global clicks (Capture Phase to beat Leaflet)
    document.addEventListener('click', (e) => {
        const searchContainer = document.querySelector('.search-container');
        // Only close if click is OUTSIDE the search box
        if (searchContainer && !searchContainer.contains(e.target)) {
            closeSearch();
        }
    }, true); // <--- capture: true is critical here
}


async function loadData() {
    showLoading(true);

    try {
        // Cache-busting timestamp for mobile browsers
        const cacheBuster = `_t=${Date.now()}`;

        // Load locations
        const taluks = await fetch(`${CONFIG.apiBase}/api/taluks?${cacheBuster}`).then(r => r.json());
        renderMarkers(taluks);

        // Load predictions (with cache-busting)
        const preds = await fetch(`${CONFIG.apiBase}/api/predictions?${cacheBuster}`).then(r => r.json());
        updatePredictions(preds);

    } catch (err) {
        console.error('Load error:', err);
    } finally {
        showLoading(false);
    }
}

function renderMarkers(data) {
    if (!data.features) return;

    // Clear existing
    Object.values(markers).forEach(m => map.removeLayer(m));
    markers = {};

    data.features.forEach(f => {
        const props = f.properties;

        // Create polygon layer
        const layer = L.geoJSON(f, {
            style: {
                fillColor: '#6b7280',
                fillOpacity: 0.5,
                color: '#94a3b8',
                weight: 1
            }
        });

        layer.bindPopup(`<b>${props.name || 'Unknown'}</b><br>Loading...`);
        layer.on('click', () => showDetails(props.taluk_id));

        layer.on('mouseover', function () {
            this.setStyle({ weight: 3, color: '#3b82f6' });
        });
        layer.on('mouseout', function () {
            this.setStyle({ weight: 1, color: '#94a3b8' });
        });

        layer.addTo(map);
        markers[props.taluk_id] = layer;
    });

    document.getElementById('totalTaluks').textContent = data.features.length;
    console.log(`Rendered ${data.features.length} polygons`);
}

function updatePredictions(data) {
    predictions = {};
    let highCount = 0;

    // Clear all existing pulse markers
    Object.values(pulseMarkers).forEach(m => map.removeLayer(m));
    pulseMarkers = {};

    if (data.predictions) {
        data.predictions.forEach(p => {
            predictions[p.taluk_id] = p;

            if (markers[p.taluk_id]) {
                markers[p.taluk_id].setStyle({
                    fillColor: p.color
                });

                markers[p.taluk_id].setPopupContent(
                    `<b>${p.taluk_name}</b><br>` +
                    `Risk: <span style="color:${p.color}">${p.risk_level}</span> (${(p.probability * 100).toFixed(1)}%)`
                );
            }

            if (p.risk_level === 'HIGH') {
                highCount++;

                // Add pulsing wave marker at centroid
                if (p.latitude && p.longitude) {
                    const pulseIcon = L.divIcon({
                        className: 'pulse-marker',
                        iconSize: [60, 60],
                        iconAnchor: [30, 30]
                    });

                    const pulseMarker = L.marker([p.latitude, p.longitude], {
                        icon: pulseIcon,
                        interactive: false
                    }).addTo(map);

                    pulseMarkers[p.taluk_id] = pulseMarker;
                }
            }
        });
    }

    document.getElementById('highRiskCount').textContent = highCount;

    if (data.last_update) {
        const time = new Date(data.last_update);
        document.getElementById('lastUpdate').textContent = time.toLocaleTimeString();
    }

    console.log(`Updated ${Object.keys(predictions).length} predictions, ${highCount} with pulse animation`);
}

let selectedTalukId = null; // Track currently selected location

function showDetails(id) {
    console.log("Clicked Taluk:", id); // Debug
    selectedTalukId = id; // Save ID for expert request
    const p = predictions[id];

    if (!p) {
        console.warn("Debug: No prediction data found for ID: " + id);
        return;
    }
    // alert("Debug: Opening Details for " + p.taluk_name + ". Scroll down for Expert Button!"); // REMOVED

    const panel = document.getElementById('infoPanel');
    const content = document.getElementById('panelContent');
    const expertControls = document.getElementById('expertControls');
    const expertResult = document.getElementById('expertResult');

    // Reset Expert View
    expertResult.innerHTML = '';
    expertResult.classList.add('hidden');
    expertControls.classList.remove('hidden');

    content.innerHTML = `
        <div style="text-align:center; margin-bottom:1rem;">
            <h3>${p.taluk_name}</h3>
            <span class="risk-badge ${p.risk_level.toLowerCase()}">${p.risk_level} RISK</span>
        </div>
        <div class="detail-row">
            <span>Probability</span>
            <span>${(p.probability * 100).toFixed(1)}%</span>
        </div>
        <div class="detail-row">
            <span>Elevation</span>
            <span>${p.dem.toFixed(1)} m</span>
        </div>
        <div class="detail-row">
            <span>Slope</span>
            <span>${p.slope.toFixed(1)}°</span>
        </div>
        <div class="detail-row">
            <span>7-Day Rain</span>
            <span>${p.rain7.toFixed(1)} mm</span>
        </div>
        <div class="detail-row">
            <span>Coordinates</span>
            <span>${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}</span>
        </div>

        <!-- Soil Saturation Removed (Deferred to V3) -->
        <!-- Rainfall Trend Graph Removed (Deferred to V3) -->
        
        <!-- Force Button Injection Removed -->
        <div id="expertResult" class="expert-result hidden" style="margin-top: 1rem; padding: 1rem; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; color: #e2e8f0;"></div>
    `;

    panel.classList.remove('hidden');

    // Ensure logic knows about these new elements (if we need to target them later)
    // The existing askExpertGeologist function uses document.getElementById('expertResult') 
    // which will now find this NEW element we just injected.
}

async function askExpertGeologist() {
    if (!selectedTalukId) return;
    const p = predictions[selectedTalukId];

    const btn = document.getElementById('btnExpert');
    const questionInput = document.getElementById('expertQuestion');
    const question = questionInput ? questionInput.value.trim() : "";

    if (!question) {
        if (!questionInput.dataset.touched) {
            // Allow empty first click
        } else {
            return;
        }
    }
    questionInput.value = '';
    questionInput.dataset.touched = "true";

    const chatHistory = document.getElementById('expertResult');
    chatHistory.classList.remove('hidden');

    // 1. Add User Bubble
    if (question) {
        chatHistory.innerHTML += `
            <div class="chat-bubble user">
                <strong>You:</strong><br>${question.replace(/\n/g, '<br>')}
            </div>
        `;
    }
    chatHistory.scrollTop = chatHistory.scrollHeight;

    // 2. Add Loading Bubble
    const loadingId = 'loading-' + Date.now();
    chatHistory.innerHTML += `
        <div class="chat-bubble ai" id="${loadingId}">
            <span class="spinner" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;"></span> 
            Analysis in progress...
        </div>
    `;
    chatHistory.scrollTop = chatHistory.scrollHeight;

    // Disable Button
    const originalText = btn.innerHTML;
    btn.disabled = true;

    try {
        const response = await fetch(`${CONFIG.apiBase}/api/ask-expert`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                taluk_id: selectedTalukId,
                lat: p.latitude,
                lon: p.longitude,
                question: question || "General Risk Assessment"
            })
        });

        const data = await response.json();
        const l = document.getElementById(loadingId);
        if (l) l.remove();

        chatHistory.innerHTML += `
            <div class="chat-bubble ai">
                <strong>🤖 Expert Geologist:</strong><br>
                ${data.analysis.replace(/\n/g, '<br>')}
            </div>
        `;
        chatHistory.scrollTop = chatHistory.scrollHeight;

    } catch (err) {
        console.error('Expert Error:', err);
        const l = document.getElementById(loadingId);
        if (l) l.innerHTML = `<span style="color:#ef4444;">Error contacting expert agent. Check backend.</span>`;
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
        if (questionInput) questionInput.focus();
    }
}

function closePanel() {
    document.getElementById('infoPanel').classList.add('hidden');
}

async function refreshData() {
    const btn = document.getElementById('refreshBtn');
    const original = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '⏳ Refreshing...';

    try {
        await fetch(`${CONFIG.apiBase}/api/refresh`, { method: 'POST' });

        // Wait a moment then fetch new data
        await new Promise(r => setTimeout(r, 1000));
        const preds = await fetch(`${CONFIG.apiBase}/api/predictions`).then(r => r.json());
        updatePredictions(preds);

        btn.innerHTML = '✅ Done!';
    } catch (err) {
        btn.innerHTML = '❌ Error';
        console.error('Refresh error:', err);
    }

    setTimeout(() => {
        btn.innerHTML = original;
        btn.disabled = false;
    }, 2000);
}

// Settings
async function openSettings() {
    const modal = document.getElementById('settingsModal');
    modal.classList.remove('hidden');

    // Load current
    try {
        const settings = await fetch(`${CONFIG.apiBase}/api/settings`).then(r => r.json());
        document.getElementById('providerSelect').value = settings.provider;
        document.getElementById('apiKeyInput').value = settings.api_key;
    } catch (e) {
        console.error('Failed to load settings', e);
    }
}

function closeSettings() {
    document.getElementById('settingsModal').classList.add('hidden');
}

async function saveSettings() {
    const provider = document.getElementById('providerSelect').value;
    const apiKey = document.getElementById('apiKeyInput').value;

    // Simple validation
    if (provider === 'openweathermap' && !apiKey) {
        alert('API Key is required for OpenWeatherMap');
        return;
    }

    try {
        await fetch(`${CONFIG.apiBase}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider: provider, api_key: apiKey })
        });

        closeSettings();

        // Trigger refresh with new settings
        refreshData();

    } catch (e) {
        alert('Failed to save settings');
    }
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.toggle('hidden', !show);
}

// Make info panel draggable
function makePanelDraggable() {
    const panel = document.getElementById('infoPanel');
    const header = panel.querySelector('.panel-header');

    let isDragging = false;
    let currentX, currentY, initialX, initialY;

    function dragStart(e) {
        if (e.type === "touchstart") {
            initialX = e.touches[0].clientX;
            initialY = e.touches[0].clientY;
        } else {
            initialX = e.clientX;
            initialY = e.clientY;
        }

        isDragging = true;
        panel.style.transition = 'none';
    }

    function drag(e) {
        if (!isDragging) return;

        e.preventDefault();

        if (e.type === "touchmove") {
            currentX = e.touches[0].clientX - initialX;
            currentY = e.touches[0].clientY - initialY;
        } else {
            currentX = e.clientX - initialX;
            currentY = e.clientY - initialY;
        }

        panel.style.transform = `translate(calc(-50% + ${currentX}px), calc(-50% + ${currentY}px))`;
    }

    function dragEnd() {
        isDragging = false;
        panel.style.transition = '';
    }

    header.addEventListener('touchstart', dragStart);
    header.addEventListener('touchmove', drag);
    header.addEventListener('touchend', dragEnd);
    header.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);
}

// Initialize drag when panel is shown
// Initialize drag when panel is shown
document.addEventListener('DOMContentLoaded', () => {
    makePanelDraggable();

    // Global click to close search
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            document.getElementById('searchResults').classList.add('hidden');
        }
    });
});

// --- Search Functionality ---
let searchDebounce = null;

function handleSearch(query) {
    const resultsDiv = document.getElementById('searchResults');

    if (query.length < 2) {
        resultsDiv.classList.add('hidden');
        return;
    }

    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
        const matches = [];
        const q = query.toLowerCase();

        // 1. Search Local Taluks
        Object.values(predictions).forEach(p => {
            if (p.taluk_name.toLowerCase().includes(q)) {
                matches.push({
                    type: 'Taluk',
                    name: p.taluk_name,
                    id: p.taluk_id,
                    lat: p.latitude,
                    lon: p.longitude
                });
            }
        });

        // 2. Add "Search Maps" option
        matches.push({
            type: 'External',
            name: `Search "${query}" on Maps`,
            query: query
        });

        renderSearchResults(matches);
    }, 300);
}

function renderSearchResults(matches) {
    const div = document.getElementById('searchResults');
    div.innerHTML = '';

    matches.forEach(m => {
        const el = document.createElement('div');
        el.className = 'search-item';
        el.innerHTML = `
            <span>${m.name}</span>
            <span class="search-type">${m.type}</span>
        `;
        el.onclick = () => executeSearch(m);
        div.appendChild(el);
    });

    div.classList.remove('hidden');
}

async function executeSearch(item) {
    document.getElementById('searchResults').classList.add('hidden');
    document.getElementById('mapSearch').value = item.name;

    if (item.type === 'Taluk') {
        // Zoom to Taluk Polygon
        if (markers[item.id]) {
            const layer = markers[item.id];
            map.fitBounds(layer.getBounds(), { padding: [50, 50] });
            layer.openPopup();
            layer.fire('click'); // Trigger details panel

            // Blink Animation (Brown dotted - User Requested)
            const blinkFunc = (l) => {
                if (l._path) {
                    l._path.classList.add('blink-brown-border');
                    setTimeout(() => {
                        l._path.classList.remove('blink-brown-border');
                    }, 5000);
                }
            };

            if (layer.eachLayer) {
                layer.eachLayer(blinkFunc);
            } else {
                blinkFunc(layer);
            }
        }
    } else if (item.type === 'External') {
        // Geocode using Nominatim (OpenStreetMap)
        try {
            const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${item.query}, Kerala, India`);
            const data = await res.json();

            if (data && data.length > 0) {
                const lat = parseFloat(data[0].lat);
                const lon = parseFloat(data[0].lon);

                map.setView([lat, lon], 14);

                // Blink Animation (Aqua dotted circle)
                blinkLocation(lat, lon);

                L.popup()
                    .setLatLng([lat, lon])
                    .setContent(`<b>${data[0].display_name}</b>`)
                    .openOn(map);
            } else {
                alert("Location not found in Kerala.");
            }
        } catch (e) {
            console.error("Geocode error", e);
            alert("Failed to search location.");
        }
    }
}

function blinkLocation(lat, lon) {
    // User requested "dot lines around that place (color - blinking brown)"

    // Clear previous blinkers
    const existing = document.querySelectorAll('.blink-brown-circle');
    existing.forEach(e => e.remove());

    const icon = L.divIcon({
        className: 'blink-brown-circle', // CSS defined in style.css
        iconSize: [60, 60],
        iconAnchor: [30, 30]
    });

    const marker = L.marker([lat, lon], {
        icon: icon,
        interactive: false
    }).addTo(map);

    // Remove after 5 seconds
    setTimeout(() => {
        map.removeLayer(marker);
        const el = document.querySelector('.blink-brown-circle');
        if (el) el.remove();
    }, 5000);
}


