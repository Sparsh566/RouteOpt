// RouteOpt Frontend Application Logic

// State Variables
let map = null;
let locations = []; // [{lat, lng, demand, name}]
let markers = [];
let routeLines = []; // Leaflet polyline layers
let animationMarkers = []; // Leaflet markers for animated vehicles
let animationIntervals = []; // Animation timers
let activeTab = 'dashboard';

// Curated colors for vehicle routes
const routeColors = [
    '#3b82f6', // blue
    '#10b981', // green
    '#f59e0b', // amber
    '#8b5cf6', // purple
    '#ec4899', // pink
    '#06b6d4', // cyan
    '#f97316', // orange
    '#14b8a6', // teal
    '#a855f7', // violet
    '#f43f5e'  // rose
];

// Document Elements
const numVehiclesInput = document.getElementById('numVehicles');
const vehicleCapacityInput = document.getElementById('vehicleCapacity');
const customCapacitiesCheck = document.getElementById('customCapacitiesCheck');
const customCapacitiesGroup = document.getElementById('customCapacitiesGroup');
const customCapacitiesInput = document.getElementById('customCapacitiesInput');
const locationList = document.getElementById('locationList');
const stopsCountBadge = document.getElementById('stopsCount');
const optimizeBtn = document.getElementById('optimizeBtn');
const clearAllBtn = document.getElementById('clearAllBtn');
const loadSampleBtn = document.getElementById('loadSampleBtn');
const routesTabBtn = document.getElementById('routesTabBtn');
const routesContainer = document.getElementById('routesContainer');
const statusDot = document.getElementById('statusDot');
const statusText = document.getElementById('statusText');
const toastContainer = document.getElementById('toastContainer');

// Results & Stats
const resTotalDistance = document.getElementById('resTotalDistance');
const resTotalDuration = document.getElementById('resTotalDuration');
const resActiveRoutes = document.getElementById('resActiveRoutes');
const resRoutingType = document.getElementById('resRoutingType');
const metricDist = document.getElementById('metricDist');
const metricTime = document.getElementById('metricTime');
const metricVehicles = document.getElementById('metricVehicles');
const mapMetricsBar = document.getElementById('mapMetricsBar');

// Simulation
const simStatus = document.getElementById('simStatus');
const startSimBtn = document.getElementById('startSimBtn');
const stopSimBtn = document.getElementById('stopSimBtn');

// Initialize Leaflet Map
function initMap() {
    // Default to Mumbai, India
    const defaultCenter = [18.9220, 72.8347];
    
    map = L.map('map', {
        zoomControl: false,
        attributionControl: false
    }).setView(defaultCenter, 12);

    // Load OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19
    }).addTo(map);

    // Put zoom control in top right
    L.control.zoom({
        position: 'topright'
    }).addTo(map);

    // Map Click Event
    map.on('click', function(e) {
        const { lat, lng } = e.latlng;
        addLocation(lat, lng);
    });

    // Check Backend Server Health
    checkBackendHealth();
}

// Check Backend Health
async function checkBackendHealth() {
    try {
        statusDot.className = 'status-dot loading';
        statusText.textContent = 'Connecting...';
        const res = await fetch('/api/health');
        if (res.ok) {
            statusDot.className = 'status-dot online';
            statusText.textContent = 'System Ready';
        } else {
            throw new Error('Server unhealthy');
        }
    } catch (e) {
        statusDot.className = 'status-dot offline';
        statusText.textContent = 'Offline Mode (Local Solver Only)';
        showToast('Running in local/offline modes. Run python backend/main.py for full OSRM capabilities.', 'warning');
        // If API fails we point to local host port 8000
        checkLocalhostBackend();
    }
}

// Fallback: check localhost directly (if running static html directly from filesystem)
async function checkLocalhostBackend() {
    try {
        const res = await fetch('http://localhost:8000/api/health');
        if (res.ok) {
            statusDot.className = 'status-dot online';
            statusText.textContent = 'Localhost Connected';
            showToast('Connected to RouteOpt Backend at localhost:8000.', 'success');
        }
    } catch (e) {
        // quiet fail
    }
}

// Helper: Get actual API base URL
function getApiUrl(path) {
    // If serving via fastapi directly, relative path is fine.
    // If opening file://, redirect to localhost:8000.
    if (window.location.protocol === 'file:') {
        return `http://localhost:8000${path}`;
    }
    return path;
}

// Add a Delivery / Depot Location
function addLocation(lat, lng, name = null, demand = null) {
    const isDepot = locations.length === 0;
    
    if (isDepot) {
        name = name || 'Central Depot';
        demand = 0;
    } else {
        name = name || `Stop #${locations.length}`;
        demand = demand !== null ? demand : Math.floor(Math.random() * 5) + 1; // random demand 1-5
    }

    const loc = { lat, lng, demand, name };
    locations.push(loc);

    // Create Leaflet Marker
    let markerIcon;
    if (isDepot) {
        markerIcon = L.divIcon({
            className: 'custom-div-icon',
            html: '<div class="marker-pin-depot"><i class="fa-solid fa-warehouse"></i></div>',
            iconSize: [32, 32],
            iconAnchor: [16, 32]
        });
    } else {
        markerIcon = L.divIcon({
            className: 'custom-div-icon',
            html: `<div class="marker-pin-stop"><span>${locations.length - 1}</span></div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 26]
        });
    }

    const marker = L.marker([lat, lng], { icon: markerIcon }).addTo(map);
    
    // Set popup
    const popupContent = `
        <div style="color:#0f172a; font-family:var(--font-sans); font-size:12px;">
            <strong>${name}</strong><br>
            ${isDepot ? 'Distribution Hub' : `Delivery Demand: ${demand} units`}<br>
            <span style="font-size:10px; color:#64748b;">${lat.toFixed(5)}, ${lng.toFixed(5)}</span>
        </div>
    `;
    marker.bindPopup(popupContent);
    markers.push(marker);

    // Update UI
    renderLocationsList();
    updateOptimizeButtonState();
    
    // Auto center map on first location (depot)
    if (isDepot) {
        map.panTo([lat, lng]);
        showToast('Depot placed. Now click the map to add delivery locations.', 'success');
    }
}

// Render Locations List in Sidebar
function renderLocationsList() {
    stopsCountBadge.textContent = `${locations.length} points`;

    if (locations.length === 0) {
        locationList.innerHTML = `
            <div class="empty-list-state">
                <i class="fa-solid fa-map-location-dot"></i>
                <p>No locations added yet</p>
                <button class="btn btn-secondary btn-sm" id="loadSampleBtnInner">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Load Mumbai Sample Data
                </button>
            </div>
        `;
        
        // Re-bind sample loader
        const loadBtnInner = document.getElementById('loadSampleBtnInner');
        if (loadBtnInner) {
            loadBtnInner.addEventListener('click', loadSampleData);
        }
        return;
    }

    let html = '';
    locations.forEach((loc, index) => {
        const isDepot = index === 0;
        html += `
            <div class="location-item ${isDepot ? 'is-depot' : ''}">
                <div class="loc-index">${isDepot ? '<i class="fa-solid fa-house"></i>' : index}</div>
                <div class="loc-details">
                    <div class="loc-name">${loc.name}</div>
                    <div class="loc-coords">${loc.lat.toFixed(5)}, ${loc.lng.toFixed(5)}</div>
                </div>
                ${!isDepot ? `
                    <div class="loc-demand-input">
                        <span>Load:</span>
                        <input type="number" min="1" max="50" value="${loc.demand}" data-index="${index}" onchange="updateStopDemand(this)">
                    </div>
                ` : '<span class="badge" style="background-color:var(--danger-glow); color:var(--danger); border:1px solid rgba(239,68,68,0.2)">DEPOT</span>'}
                <button class="loc-remove-btn" onclick="removeLocation(${index})" title="Remove location">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
        `;
    });
    locationList.innerHTML = html;
}

// Update stop demand
window.updateStopDemand = function(inputEl) {
    const idx = parseInt(inputEl.getAttribute('data-index'));
    const val = parseInt(inputEl.value);
    if (!isNaN(val) && val > 0) {
        locations[idx].demand = val;
        
        // Update popup
        const marker = markers[idx];
        const popupContent = `
            <div style="color:#0f172a; font-family:var(--font-sans); font-size:12px;">
                <strong>${locations[idx].name}</strong><br>
                Delivery Demand: ${val} units<br>
                <span style="font-size:10px; color:#64748b;">${locations[idx].lat.toFixed(5)}, ${locations[idx].lng.toFixed(5)}</span>
            </div>
        `;
        marker.setPopupContent(popupContent);
    }
};

// Remove a specific location
window.removeLocation = function(index) {
    // If removing depot (index 0), clear everything
    if (index === 0) {
        clearAll();
        return;
    }

    // Remove map marker
    map.removeLayer(markers[index]);

    // Slice array
    locations.splice(index, 1);
    markers.splice(index, 1);

    // Re-index remaining markers and popups
    for (let i = 1; i < markers.length; i++) {
        // Redraw marker icon to update numbers
        const markerIcon = L.divIcon({
            className: 'custom-div-icon',
            html: `<div class="marker-pin-stop"><span>${i}</span></div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 26]
        });
        markers[i].setIcon(markerIcon);
        
        // Update locations name
        if (locations[i].name.startsWith('Stop #')) {
            locations[i].name = `Stop #${i}`;
        }
    }

    renderLocationsList();
    updateOptimizeButtonState();
    clearRoutesFromMap();
};

// Enable/Disable Optimize Button
function updateOptimizeButtonState() {
    // Need at least 1 Depot and 1 Stop to run optimization
    optimizeBtn.disabled = locations.length < 2;
}

// Load Sample Data (Mumbai, India)
function loadSampleData() {
    clearAll();

    // Depot: Gateway of India
    addLocation(18.9220, 72.8347, 'Gateway of India Hub', 0);
    
    // Stops
    addLocation(18.9400, 72.8354, 'CST Station Express', 4);
    addLocation(18.9430, 72.8230, 'Marine Drive Point', 6);
    addLocation(18.9100, 72.8280, 'Colaba Retail', 3);
    addLocation(18.9543, 72.8115, 'Girgaon Chowpatty Outlet', 5);
    addLocation(18.9472, 72.8331, 'Crawford Market Center', 2);
    addLocation(18.9548, 72.7985, 'Malabar Hill Estate', 4);
    addLocation(18.9750, 72.8300, 'Byculla Dispatch Hub', 5);

    // Fit map bounds to show all coordinates
    const group = new L.featureGroup(markers);
    map.fitBounds(group.getBounds().pad(0.1));
    showToast('Mumbai delivery sample loaded. Click Optimize Routes!', 'success');
}

// Clear all markers and routes
function clearAll() {
    // Stop simulations if running
    stopSimulation();

    // Clear map layers
    markers.forEach(m => map.removeLayer(m));
    clearRoutesFromMap();

    locations = [];
    markers = [];

    renderLocationsList();
    updateOptimizeButtonState();

    // Disable routes tab
    routesTabBtn.disabled = true;
    switchTab('dashboard');

    mapMetricsBar.classList.add('hidden');
}

function clearRoutesFromMap() {
    routeLines.forEach(l => map.removeLayer(l));
    routeLines = [];
}

// Custom capacities checkbox trigger
customCapacitiesCheck.addEventListener('change', function() {
    if (this.checked) {
        customCapacitiesGroup.classList.remove('hidden');
    } else {
        customCapacitiesGroup.classList.add('hidden');
    }
});

// Run Route Optimization API call
async function optimizeRoutes() {
    if (locations.length < 2) return;

    // Get configs
    const numVehicles = parseInt(numVehiclesInput.value);
    let capacities = [];

    if (customCapacitiesCheck.checked) {
        const text = customCapacitiesInput.value;
        capacities = text.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
        if (capacities.length !== numVehicles) {
            showToast(`Custom capacities count (${capacities.length}) must match the number of vehicles (${numVehicles})`, 'error');
            return;
        }
    } else {
        const cap = parseInt(vehicleCapacityInput.value);
        capacities = Array(numVehicles).fill(cap);
    }

    // Set UI state to loading
    optimizeBtn.disabled = true;
    optimizeBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Solving...';
    statusDot.className = 'status-dot loading';
    statusText.textContent = 'Solving VRP...';

    // Build payload
    const payload = {
        locations: locations,
        num_vehicles: numVehicles,
        vehicle_capacities: capacities
    };

    try {
        const response = await fetch(getApiUrl('/api/optimize'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Optimization failed');
        }

        // Optimization successful!
        showToast('Route optimization completed successfully!', 'success');
        renderOptimizationResults(data);

        // Switch to Routes Tab
        routesTabBtn.disabled = false;
        switchTab('routes');

    } catch (e) {
        loggerError(e);
        showToast(e.message || 'Error occurred while optimization solver ran.', 'error');
    } finally {
        optimizeBtn.disabled = false;
        optimizeBtn.innerHTML = '<i class="fa-solid fa-bolt"></i> Optimize Routes';
        checkBackendHealth();
    }
}

// Render Results on Map and Sidebar
function renderOptimizationResults(data) {
    clearRoutesFromMap();
    stopSimulation();

    // 1. Update stats readouts
    const distKm = (data.total_distance_meters / 1000).toFixed(2);
    const durationMins = Math.round(data.total_duration_seconds / 60);
    const activeRoutes = data.routes.filter(r => r.node_sequence.length > 0).length;

    resTotalDistance.textContent = `${distKm} km`;
    resTotalDuration.textContent = `${durationMins} mins`;
    resActiveRoutes.textContent = `${activeRoutes} / ${data.routes.length}`;
    resRoutingType.textContent = data.using_real_roads ? 'OSM Road Path' : 'Haversine Fallback';

    // Map floating metrics bar
    metricDist.textContent = `${distKm} km`;
    metricTime.textContent = `${durationMins} mins`;
    metricVehicles.textContent = `${activeRoutes} Active`;
    mapMetricsBar.classList.remove('hidden');

    // 2. Render route lines on the map & construct route list HTML
    let routesHtml = '';
    const bounds = [];

    // Save solver response routes globally for animator access
    window.optimizedRoutes = data.routes;

    data.routes.forEach((route, index) => {
        const color = routeColors[index % routeColors.length];
        
        if (route.node_sequence.length === 0) {
            routesHtml += `
                <div class="card route-card" style="--route-color: var(--text-muted); opacity: 0.5;">
                    <div class="route-header">
                        <span class="route-title"><i class="fa-solid fa-truck"></i> Vehicle #${index + 1}</span>
                        <span class="badge">Unused</span>
                    </div>
                    <p style="font-size:12px; color:var(--text-muted);">No stops allocated due to sufficient capacity on other routes.</p>
                </div>
            `;
            return;
        }

        // Draw Polyline Route on map
        let polylinePoints = [];
        
        if (route.geometry && route.geometry.coordinates && route.geometry.coordinates.length > 0) {
            // OSRM coordinates are [lon, lat], Leaflet expects [lat, lon]
            polylinePoints = route.geometry.coordinates.map(coord => [coord[1], coord[0]]);
        } else {
            // Straight-line fallback
            polylinePoints = route.node_sequence.map(nodeIdx => [locations[nodeIdx].lat, locations[nodeIdx].lng]);
        }

        // Create Leaflet Polyline
        const polyline = L.polyline(polylinePoints, {
            color: color,
            weight: 5,
            opacity: 0.85,
            dashArray: index % 2 === 1 ? '10, 8' : null // differentiate line styles
        }).addTo(map);

        routeLines.push(polyline);
        
        // Push bounds for fitting map view
        polylinePoints.forEach(p => bounds.push(p));

        // Calculate load percentage
        const loadPercent = Math.min(100, Math.round((route.load / route.capacity) * 100));

        // Generate Stop Sequence HTML
        let stopsHtml = '';
        route.node_sequence.forEach((nodeIdx, seqIdx) => {
            const isDepot = nodeIdx === 0;
            const isLast = seqIdx === route.node_sequence.length - 1;
            
            stopsHtml += `
                <div class="route-stop-node ${isDepot ? 'is-depot' : ''}">
                    <i class="fa-solid ${isDepot ? 'fa-warehouse' : 'fa-circle'}"></i>
                    <span>${locations[nodeIdx].name} ${!isDepot ? `(Load: ${locations[nodeIdx].demand})` : ''}</span>
                    ${!isLast ? '<i class="fa-solid fa-arrow-right-long" style="font-size:10px; margin: 0 4px; color:var(--text-muted)"></i>' : ''}
                </div>
            `;
        });

        // Add details card
        routesHtml += `
            <div class="card route-card" style="--route-color: ${color}">
                <div class="route-header">
                    <span class="route-title"><i class="fa-solid fa-truck"></i> Vehicle #${index + 1}</span>
                    <span class="badge" style="background-color: ${color}20; color: ${color}; border: 1px solid ${color}40">
                        ${route.node_sequence.length - 2} deliveries
                    </span>
                </div>
                
                <div class="route-metrics">
                    <span><i class="fa-solid fa-road"></i> ${(route.distance_meters/1000).toFixed(1)} km</span>
                    <span><i class="fa-solid fa-clock"></i> ${Math.round(route.duration_seconds/60)} mins</span>
                </div>

                <div class="capacity-bar-container">
                    <div class="capacity-label-row">
                        <span>Capacity Utilized: ${route.load} / ${route.capacity} units</span>
                        <span>${loadPercent}%</span>
                    </div>
                    <div class="capacity-bar-bg">
                        <div class="capacity-bar-fill ${loadPercent > 100 ? 'overloaded' : ''}" style="width: ${loadPercent}%; --route-color: ${color}"></div>
                    </div>
                </div>

                <div class="route-stops-list">
                    <strong>Stop Dispatch Sequence:</strong>
                    <div style="display:flex; flex-wrap:wrap; align-items:center; gap: 4px; margin-top: 4px;">
                        ${stopsHtml}
                    </div>
                </div>
            </div>
        `;
    });

    routesContainer.innerHTML = routesHtml;

    // Adjust Map view to fit all routes
    if (bounds.length > 0) {
        map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50] });
    }
}

// Animation Delivery Simulation Loop
function startSimulation() {
    stopSimulation(); // clear old animations

    if (!window.optimizedRoutes) {
        showToast('No optimized routes found to simulate.', 'error');
        return;
    }

    simStatus.classList.remove('hidden');
    startSimBtn.classList.add('hidden');
    stopSimBtn.classList.remove('hidden');

    window.optimizedRoutes.forEach((route, index) => {
        if (route.node_sequence.length === 0) return;

        const color = routeColors[index % routeColors.length];
        let pathPoints = [];

        if (route.geometry && route.geometry.coordinates && route.geometry.coordinates.length > 0) {
            // Road paths
            pathPoints = route.geometry.coordinates.map(c => [c[1], c[0]]);
        } else {
            // Straight lines fallback
            pathPoints = route.node_sequence.map(nodeIdx => [locations[nodeIdx].lat, locations[nodeIdx].lng]);
        }

        if (pathPoints.length < 2) return;

        // Create anim vehicle marker
        const vehicleIcon = L.divIcon({
            className: 'custom-div-icon',
            html: `<div class="sim-vehicle-dot" style="--vehicle-color: ${color}"></div>`,
            iconSize: [14, 14],
            iconAnchor: [7, 7]
        });

        const vehicleMarker = L.marker(pathPoints[0], { icon: vehicleIcon }).addTo(map);
        animationMarkers.push(vehicleMarker);

        // Animation tracking details
        let currentStep = 0;
        const totalSteps = pathPoints.length;
        
        // Speed up timer for long coordinates arrays, slow down for small straight-line fallbacks
        const speedMs = pathPoints.length > 50 ? 40 : 150;

        const interval = setInterval(() => {
            currentStep++;
            if (currentStep >= totalSteps) {
                // Restart route animation (looping)
                currentStep = 0;
            }
            
            // Move marker smoothly
            vehicleMarker.setLatLng(pathPoints[currentStep]);
        }, speedMs);

        animationIntervals.push(interval);
    });

    showToast('Delivery simulation started.', 'success');
}

function stopSimulation() {
    simStatus.classList.add('hidden');
    startSimBtn.classList.remove('hidden');
    stopSimBtn.classList.add('hidden');

    // Clear timers
    animationIntervals.forEach(clearInterval);
    animationIntervals = [];

    // Clear map markers
    animationMarkers.forEach(m => map.removeLayer(m));
    animationMarkers = [];
}

// Tab switcher
function switchTab(tabId) {
    activeTab = tabId;
    
    // Tabs buttons CSS
    document.querySelectorAll('.nav-tab').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Content pane CSS
    document.querySelectorAll('.tab-pane').forEach(pane => {
        if (pane.id === `tab-${tabId}`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });
}

// Toast Notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconClass = 'fa-circle-info';
    if (type === 'success') iconClass = 'fa-circle-check text-success';
    if (type === 'error') iconClass = 'fa-triangle-exclamation text-danger';
    if (type === 'warning') iconClass = 'fa-circle-exclamation text-warning';

    toast.innerHTML = `
        <div style="display:flex; align-items:center; gap:8px;">
            <i class="fa-solid ${iconClass}"></i>
            <span>${message}</span>
        </div>
        <button class="toast-close"><i class="fa-solid fa-xmark"></i></button>
    `;

    toastContainer.appendChild(toast);

    // Event listener to close
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.remove();
    });

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Logger helper
function loggerError(err) {
    console.error('[RouteOpt Error]', err);
}

// Event Bindings
document.querySelectorAll('.nav-tab').forEach(btn => {
    btn.addEventListener('click', () => {
        switchTab(btn.getAttribute('data-tab'));
    });
});

optimizeBtn.addEventListener('click', optimizeRoutes);
clearAllBtn.addEventListener('click', clearAll);
loadSampleBtn.addEventListener('click', loadSampleData);
startSimBtn.addEventListener('click', startSimulation);
stopSimBtn.addEventListener('click', stopSimulation);

// Window level helper functions
window.addEventListener('load', initMap);
