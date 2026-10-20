/**
 * RouteOpt - Commercial Fleet Routing & Dispatch System
 * Features:
 * 1. Multi-vehicle CVRPTW with Van and Truck road rules.
 * 2. AI What-If Scenario simulation with preset and custom problem analysis.
 * 3. Live Driver Route Animation on map.
 */

// Application State
const state = {
    depot: null,
    stops: [],
    fleet: {
        vans: 2,
        trucks: 1
    },
    departureHour: 8.5, // 08:30 AM
    currentRoutes: [],
    selectedScenario: "BORDER_ENTRY_DELAY",
    map: null,
    markersLayer: null,
    routesLayer: null,
    
    // Regulatory spatial layers
    geofenceLayer: null,
    barriersLayer: null,
    bridgesLayer: null,
    lastOptimizationData: null,
    
    // Animation tracking
    animationMarkers: [],
    animationIntervals: [],
    isAnimating: false
};

// Mumbai Metropolitan Regulatory Geofence (Greater Mumbai Urban Core)
const MUMBAI_GEOFENCE_COORDS = [
    [19.2550, 72.8600], // Dahisar Border Checkpost (North-West)
    [19.2300, 72.9150], // Sanjay Gandhi National Park Ridge
    [19.1750, 72.9580], // Mulund Border Checkpost (North-East)
    [19.1200, 72.9400], // Bhandup / Kanjurmarg East
    [19.0600, 72.9380], // Mankhurd / Vashi Creek Gate (East)
    [19.0150, 72.8850], // Wadala / Port Trust Corridor
    [18.9100, 72.8250], // Colaba / South Mumbai Tip
    [18.9300, 72.8150], // Nariman Point / Marine Drive
    [19.0150, 72.8150], // Worli Seaface
    [19.0600, 72.8250], // Bandra West
    [19.1350, 72.8150], // Juhu / Versova Coastline
    [19.2000, 72.8350], // Malad / Kandivali West
    [19.2550, 72.8600]  // Back to Dahisar Checkpost
];

// Structural Road Barriers (Flyover Height Gantries & Bridge Load Limits)
const REGULATORY_BARRIERS = [
    {
        type: "height_gantry",
        name: "JJ Flyover Overhead Clearance Gantry",
        lat: 18.9550,
        lon: 72.8360,
        height_limit_m: 2.5,
        rule_details: "2.5m Max Clearance. Heavy freight trucks (Tata 407, Eicher) barred; must divert via P D'Mello Road ground-level arterial.",
        penalty: "Collision hazard with overhead gantry / MVA Sec 115 fine"
    },
    {
        type: "height_gantry",
        name: "Kalanagar Junction Flyover (Bandra East)",
        lat: 19.0580,
        lon: 72.8520,
        height_limit_m: 2.5,
        rule_details: "2.5m Steel Clearance Gantry. Only delivery vans (Tata Ace) allowed on flyover. Heavy trucks restricted to surface grade.",
        penalty: "+35% transit delay on surface road"
    },
    {
        type: "height_gantry",
        name: "Amar Mahal Junction Flyover (Chembur)",
        lat: 19.0680,
        lon: 72.8980,
        height_limit_m: 2.5,
        rule_details: "2.5m Clearance Bar. Freight trucks diverted to ground-level roundabout.",
        penalty: "Low clearance obstruction hazard"
    },
    {
        type: "height_gantry",
        name: "Sion Circle Overhead Clearance Bar",
        lat: 19.0380,
        lon: 72.8620,
        height_limit_m: 2.5,
        rule_details: "2.5m Height Clearance Bar. Surface detour mandatory for trucks.",
        penalty: "Traffic obstruction penalty"
    },
    {
        type: "bridge_weight",
        name: "Sion-Bandra Link Road Old Bridge",
        lat: 19.0430,
        lon: 72.8580,
        weight_limit_t: 7.5,
        rule_details: "7.5 Tonnes Gross Vehicle Weight (GVW) Restriction. Old infrastructure span prohibits multi-axle heavy trucks.",
        penalty: "Structural breach risk - Mandatory bypass via Eastern Freeway"
    },
    {
        type: "bridge_weight",
        name: "Reay Road Rail Overbridge",
        lat: 18.9730,
        lon: 72.8420,
        weight_limit_t: 7.5,
        rule_details: "7.5 Tonnes Maximum Axle Rating. Heavy trucks must divert via Harbour bypass.",
        penalty: "Weight restriction enforcement"
    }
];

// Preset Mumbai Transport Dataset
const MUMBAI_PRESET = {
    depot: {
        depot_id: "DEPOT-BHIWANDI",
        name: "Bhiwandi Central Freight Hub",
        lat: 19.2967,
        lon: 73.0631,
        operating_hours_sec: 43200
    },
    stops: [
        {
            stop_id: "STOP-01",
            name: "Mulund Commercial Checkpost",
            lat: 19.1726,
            lon: 72.9565,
            demand_kg: 450,
            time_window_start_sec: 0,
            time_window_end_sec: 36000,
            service_duration_sec: 600,
            is_in_restricted_urban_core: true
        },
        {
            stop_id: "STOP-02",
            name: "Dadar Wholesale Goods Market",
            lat: 19.0178,
            lon: 72.8478,
            demand_kg: 600,
            time_window_start_sec: 1800,
            time_window_end_sec: 43200,
            service_duration_sec: 900,
            is_in_restricted_urban_core: true
        },
        {
            stop_id: "STOP-03",
            name: "Bandra Kurla Complex (BKC) Bay",
            lat: 19.0674,
            lon: 72.8687,
            demand_kg: 350,
            time_window_start_sec: 3600,
            time_window_end_sec: 36000,
            service_duration_sec: 450,
            is_in_restricted_urban_core: true
        },
        {
            stop_id: "STOP-04",
            name: "Andheri East MIDC Industrial Estate",
            lat: 19.1136,
            lon: 72.8697,
            demand_kg: 500,
            time_window_start_sec: 1800,
            time_window_end_sec: 43200,
            service_duration_sec: 600,
            is_in_restricted_urban_core: true
        },
        {
            stop_id: "STOP-05",
            name: "Vashi APMC Freight Hub (Navi Mumbai)",
            lat: 19.0760,
            lon: 72.9986,
            demand_kg: 800,
            time_window_start_sec: 0,
            time_window_end_sec: 43200,
            service_duration_sec: 750,
            is_in_restricted_urban_core: false
        },
        {
            stop_id: "STOP-06",
            name: "Thane West Distribution Warehouse",
            lat: 19.2183,
            lon: 72.9781,
            demand_kg: 300,
            time_window_start_sec: 0,
            time_window_end_sec: 43200,
            service_duration_sec: 300,
            is_in_restricted_urban_core: false
        }
    ]
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    initMap();
    initEventListeners();
    updateClockDisplay(state.departureHour);
    updateFleetSummary();
    loadMumbaiPreset();
});

// Initialize Leaflet Map
function initMap() {
    state.map = L.map("map", {
        center: [19.1400, 72.9700],
        zoom: 11,
        zoomControl: false
    });

    L.control.zoom({ position: "bottomright" }).addTo(state.map);

    // Completely free OpenStreetMap tile server
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19
    }).addTo(state.map);

    state.markersLayer = L.layerGroup().addTo(state.map);
    state.routesLayer = L.layerGroup().addTo(state.map);
    state.geofenceLayer = L.layerGroup().addTo(state.map);
    state.barriersLayer = L.layerGroup().addTo(state.map);
    state.bridgesLayer = L.layerGroup().addTo(state.map);

    initRegulatoryLayers();

    state.map.on("click", (e) => {
        handleMapClick(e.latlng.lat, e.latlng.lng);
    });
}

// Event Listeners
function initEventListeners() {
    // Navigation Tabs
    document.querySelectorAll(".nav-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            if (tab.disabled) return;
            document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
            
            tab.classList.add("active");
            const target = document.getElementById("tab-" + tab.dataset.tab);
            if (target) target.classList.add("active");
        });
    });

    // Time Slider
    const slider = document.getElementById("shiftTimeSlider");
    slider.addEventListener("input", (e) => {
        state.departureHour = parseFloat(e.target.value);
        updateClockDisplay(state.departureHour);
    });

    // Vehicle Counter Controls
    document.getElementById("btnIncVan").addEventListener("click", () => {
        state.fleet.vans = Math.min(6, state.fleet.vans + 1);
        document.getElementById("vanCount").textContent = state.fleet.vans;
        updateFleetSummary();
    });
    document.getElementById("btnDecVan").addEventListener("click", () => {
        state.fleet.vans = Math.max(0, state.fleet.vans - 1);
        document.getElementById("vanCount").textContent = state.fleet.vans;
        updateFleetSummary();
    });

    document.getElementById("btnIncTruck").addEventListener("click", () => {
        state.fleet.trucks = Math.min(4, state.fleet.trucks + 1);
        document.getElementById("truckCount").textContent = state.fleet.trucks;
        updateFleetSummary();
    });
    document.getElementById("btnDecTruck").addEventListener("click", () => {
        state.fleet.trucks = Math.max(0, state.fleet.trucks - 1);
        document.getElementById("truckCount").textContent = state.fleet.trucks;
        updateFleetSummary();
    });

    // Preset & Reset
    document.getElementById("loadSampleBtn").addEventListener("click", loadMumbaiPreset);
    document.getElementById("clearBtn").addEventListener("click", clearAll);

    // Optimize Button
    document.getElementById("optimizeBtn").addEventListener("click", optimizeRoutes);

    // Preset Scenario Selection
    document.querySelectorAll(".scenario-card").forEach(card => {
        card.addEventListener("click", () => {
            document.querySelectorAll(".scenario-card").forEach(c => {
                c.classList.remove("active");
                c.querySelector(".scenario-radio i").className = "fa-regular fa-circle";
            });
            card.classList.add("active");
            card.querySelector(".scenario-radio i").className = "fa-solid fa-circle-dot";
            state.selectedScenario = card.dataset.scenario;
        });
    });

    // Custom Situation Suggestion Chips
    document.querySelectorAll(".chip-btn").forEach(chip => {
        chip.addEventListener("click", () => {
            const textarea = document.getElementById("customSituationInput");
            textarea.value = chip.dataset.text;
            textarea.focus();
            showToast("Loaded sample problem into textarea", "info");
        });
    });

    // Run Preset Simulation
    document.getElementById("runSimulationBtn").addEventListener("click", () => runSimulationRequest(null));

    // Run Custom User Problem Simulation
    document.getElementById("runCustomSimulationBtn").addEventListener("click", () => {
        const customText = document.getElementById("customSituationInput").value.trim();
        if (!customText) {
            showToast("Please type a situation or road problem to analyze.", "warning");
            document.getElementById("customSituationInput").focus();
            return;
        }
        runSimulationRequest(customText);
    });

    // Direct Start Simulation Button in Dispatch tab
    document.getElementById("directSimBtn")?.addEventListener("click", async () => {
        if (!state.currentRoutes || state.currentRoutes.length === 0) {
            await optimizeRoutes();
        }
        startRouteAnimation();
    });

    // Watch Driver Movement button inside Simulation Result card
    document.getElementById("simWatchDriverBtn")?.addEventListener("click", async () => {
        if (!state.currentRoutes || state.currentRoutes.length === 0) {
            await optimizeRoutes();
        }
        startRouteAnimation();
        showToast("Tracking active vehicles on map.", "info");
    });

    // Animation Controls
    document.getElementById("startMapAnimBtn").addEventListener("click", startRouteAnimation);
    document.getElementById("stopMapAnimBtn").addEventListener("click", stopRouteAnimation);
    document.getElementById("itineraryPlayAnimBtn")?.addEventListener("click", async () => {
        if (!state.currentRoutes || state.currentRoutes.length === 0) {
            await optimizeRoutes();
        }
        startRouteAnimation();
        showToast("Switched to map view. Driver route animation started.", "info");
    });

    // Speed Controls (1x, 2x, 4x)
    document.querySelectorAll(".btn-speed").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".btn-speed").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            state.animationSpeed = parseInt(btn.dataset.speed, 10) || 1;
            if (state.isAnimating) {
                startRouteAnimation();
            }
        });
    });

    // Export / Print Dispatch Manifest
    document.getElementById("exportManifestBtn")?.addEventListener("click", () => {
        if (!state.lastOptimizationData || !state.lastOptimizationData.routes || state.lastOptimizationData.routes.length === 0) {
            showToast("Please calculate optimal routes first to generate the manifest.", "warning");
            return;
        }
        renderManifestModal(state.lastOptimizationData);
        document.getElementById("manifestModalBackdrop")?.classList.remove("hidden");
    });

    document.getElementById("closeManifestBtn")?.addEventListener("click", () => {
        document.getElementById("manifestModalBackdrop")?.classList.add("hidden");
    });

    document.getElementById("manifestModalBackdrop")?.addEventListener("click", (e) => {
        if (e.target.id === "manifestModalBackdrop") {
            document.getElementById("manifestModalBackdrop").classList.add("hidden");
        }
    });

    document.getElementById("printManifestBtn")?.addEventListener("click", () => {
        window.print();
    });

    document.getElementById("downloadCsvBtn")?.addEventListener("click", downloadManifestCsv);
}

// Update Clock Display and Traffic Regulation Status
function updateClockDisplay(hourVal) {
    const hours = Math.floor(hourVal);
    const mins = (hourVal % 1) * 60;
    const ampm = hours >= 12 ? "PM" : "AM";
    const displayHour = hours % 12 === 0 ? 12 : hours % 12;
    const timeStr = `${String(displayHour).padStart(2, "0")}:${String(mins).padStart(2, "0")} ${ampm}`;
    
    document.getElementById("clockDisplay").textContent = timeStr;

    const statusBox = document.getElementById("ruleStatusBox");
    const statusTitle = document.getElementById("ruleStatusTitle");
    const statusDesc = document.getElementById("ruleStatusDesc");

    if (hourVal >= 8.0 && hourVal <= 11.5) {
        statusBox.className = "rule-status-box status-restricted";
        statusTitle.textContent = "MORNING NO-ENTRY ACTIVE (08:00 AM - 11:30 AM)";
        statusDesc.textContent = "Heavy freight trucks (Tata 407) are banned in city limits. Illegal entry risks Rs 20,000 fine. Small delivery vans (Tata Ace) are allowed.";
    } else if (hourVal >= 17.0 && hourVal <= 21.5) {
        statusBox.className = "rule-status-box status-restricted";
        statusTitle.textContent = "EVENING NO-ENTRY ACTIVE (05:00 PM - 09:30 PM)";
        statusDesc.textContent = "Severe peak ban on heavy goods vehicles. Only small delivery vans under 3.5 tonnes GVW are permitted.";
    } else {
        statusBox.className = "rule-status-box status-open";
        statusTitle.textContent = "ALL ROADS OPEN (UNRESTRICTED)";
        statusDesc.textContent = "Both delivery vans and heavy freight trucks are permitted on all designated commercial arterial roads.";
    }
}

// Update Fleet Summary
function updateFleetSummary() {
    const tag = document.getElementById("fleetSummaryTag");
    tag.textContent = `${state.fleet.vans} Vans, ${state.fleet.trucks} Trucks`;
    
    const optimizeBtn = document.getElementById("optimizeBtn");
    const hasVehicles = (state.fleet.vans + state.fleet.trucks) > 0;
    const hasStops = state.stops.length > 0 && state.depot !== null;
    optimizeBtn.disabled = !(hasVehicles && hasStops);
}

// Load Mumbai Logistics Preset
function loadMumbaiPreset() {
    stopRouteAnimation();
    state.depot = { ...MUMBAI_PRESET.depot };
    state.stops = JSON.parse(JSON.stringify(MUMBAI_PRESET.stops));
    renderLocationsList();
    renderMapMarkers();
    updateFleetSummary();
    showToast("Loaded Mumbai transport dataset (Bhiwandi Hub and 6 drop locations)", "success");
}

// Clear All Stops
function clearAll() {
    stopRouteAnimation();
    state.depot = null;
    state.stops = [];
    state.currentRoutes = [];
    state.markersLayer.clearLayers();
    state.routesLayer.clearLayers();
    renderLocationsList();
    updateFleetSummary();
    document.getElementById("itineraryTabBtn").disabled = true;
    document.getElementById("mapMetricsBar").classList.add("hidden");
    document.getElementById("mapAnimBar").classList.add("hidden");
    showToast("Reset all locations", "warning");
}

// Handle Map Clicks
function handleMapClick(lat, lon) {
    if (!state.depot) {
        state.depot = {
            depot_id: "DEPOT-CUSTOM",
            name: "Central Logistics Hub",
            lat: lat,
            lon: lon,
            operating_hours_sec: 43200
        };
        showToast("Set warehouse hub location", "success");
    } else {
        const idx = state.stops.length + 1;
        state.stops.push({
            stop_id: `STOP-${String(idx).padStart(2, "0")}`,
            name: `Delivery Drop Point ${idx}`,
            lat: lat,
            lon: lon,
            demand_kg: 400,
            time_window_start_sec: 0,
            time_window_end_sec: 43200,
            service_duration_sec: 600,
            is_in_restricted_urban_core: true
        });
        showToast(`Added Drop Point ${idx}`, "success");
    }
    renderLocationsList();
    renderMapMarkers();
    updateFleetSummary();
}

// Render Locations List in Sidebar
function renderLocationsList() {
    const list = document.getElementById("locationList");
    const stopsCount = document.getElementById("stopsCount");
    
    if (!state.depot && state.stops.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-map"></i>
                <p>No delivery locations loaded.</p>
                <button class="btn btn-secondary btn-sm" id="loadSampleBtnInline">
                    <i class="fa-solid fa-download"></i> Load Mumbai Transport Dataset
                </button>
            </div>
        `;
        document.getElementById("loadSampleBtnInline")?.addEventListener("click", loadMumbaiPreset);
        stopsCount.textContent = "0 stops";
        return;
    }

    stopsCount.textContent = `${state.stops.length} drops`;
    let html = "";

    if (state.depot) {
        html += `
            <div class="stop-card">
                <div class="stop-badge-num hub-badge"><i class="fa-solid fa-warehouse"></i></div>
                <div class="stop-meta">
                    <div class="stop-meta-name">${state.depot.name}</div>
                    <div class="stop-meta-info">Main Warehouse Hub - Starting & Ending Point</div>
                </div>
            </div>
        `;
    }

    state.stops.forEach((s, i) => {
        const zoneText = s.is_in_restricted_urban_core ? "City Core (Restricted)" : "Outer Highway";
        html += `
            <div class="stop-card">
                <div class="stop-badge-num">${i + 1}</div>
                <div class="stop-meta">
                    <div class="stop-meta-name">${s.name}</div>
                    <div class="stop-meta-info">Load: ${s.demand_kg} kg | Unload: ${Math.round(s.service_duration_sec / 60)} mins | ${zoneText}</div>
                </div>
            </div>
        `;
    });

    list.innerHTML = html;
}

// Render Map Markers
function renderMapMarkers() {
    state.markersLayer.clearLayers();
    const bounds = [];

    if (state.depot) {
        const depotIcon = L.divIcon({
            className: "custom-depot-marker",
            html: `<div style="background:#2563eb; color:#ffffff; width:32px; height:32px; border-radius:4px; display:flex; align-items:center; justify-content:center; border:2px solid #ffffff; font-size:14px;"><i class="fa-solid fa-warehouse"></i></div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });
        const marker = L.marker([state.depot.lat, state.depot.lon], { icon: depotIcon })
            .bindPopup(`<strong>${state.depot.name}</strong><br>Warehouse Hub`);
        state.markersLayer.addLayer(marker);
        bounds.push([state.depot.lat, state.depot.lon]);
    }

    state.stops.forEach((s, i) => {
        const stopIcon = L.divIcon({
            className: "custom-stop-marker",
            html: `<div style="background:#0f172a; color:#38bdf8; width:26px; height:26px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:11px; border:2px solid #38bdf8;">${i + 1}</div>`,
            iconSize: [26, 26],
            iconAnchor: [13, 13]
        });
        const marker = L.marker([s.lat, s.lon], { icon: stopIcon })
            .bindPopup(`<strong>Stop ${i + 1}: ${s.name}</strong><br>Weight: ${s.demand_kg} kg<br>Zone: ${s.is_in_restricted_urban_core ? "City Core" : "Outer Arterial"}`);
        state.markersLayer.addLayer(marker);
        bounds.push([s.lat, s.lon]);
    });

    if (bounds.length > 0) {
        state.map.fitBounds(bounds, { padding: [40, 40] });
    }
}

// Build Fleet Spec
function buildFleetSpec() {
    const fleet = [];
    for (let i = 0; i < state.fleet.vans; i++) {
        fleet.push({
            vehicle_id: `VAN-${String(i + 1).padStart(2, "0")}`,
            name: `Tata Ace Van ${i + 1}`,
            vehicle_class: "van",
            gross_vehicle_weight_tonnes: 2.2,
            height_meters: 1.9,
            payload_capacity_kg: 1200.0,
            fixed_dispatch_cost: 250.0,
            running_cost_per_km: 12.0,
            color_hex: "#0284c7" // Solid blue
        });
    }
    for (let i = 0; i < state.fleet.trucks; i++) {
        fleet.push({
            vehicle_id: `TRUCK-${String(i + 1).padStart(2, "0")}`,
            name: `Tata 407 Truck ${i + 1}`,
            vehicle_class: "truck",
            gross_vehicle_weight_tonnes: 7.2,
            height_meters: 3.1,
            payload_capacity_kg: 4500.0,
            fixed_dispatch_cost: 600.0,
            running_cost_per_km: 22.0,
            color_hex: "#d97706" // Solid amber
        });
    }
    return fleet;
}

// Calculate Optimal Routes
async function optimizeRoutes(autoSwitchTab = true) {
    stopRouteAnimation();
    const btn = document.getElementById("optimizeBtn");
    const btnText = document.getElementById("optimizeBtnText");
    btn.disabled = true;
    btnText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Calculating Routes...';

    const fleet = buildFleetSpec();
    const payload = {
        depot: state.depot,
        stops: state.stops,
        fleet: fleet,
        departure_time_iso: "2026-10-09T08:30:00+05:30",
        region: "MUMBAI_MMRDA",
        apply_traffic_congestion: true,
        enforce_government_guidelines: true
    };

    try {
        const res = await fetch("/api/optimize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Route calculation failed");
        }

        const data = await res.json();
        handleOptimizationSuccess(data, autoSwitchTab);
    } catch (err) {
        showToast(`Error: ${err.message}`, "error");
    } finally {
        btn.disabled = false;
        btnText.innerHTML = '<i class="fa-solid fa-check"></i> Calculate Optimal Routes';
    }
}

// Handle Optimization Success
function handleOptimizationSuccess(data, autoSwitchTab = true) {
    state.lastOptimizationData = data;
    state.currentRoutes = data.routes;
    state.routesLayer.clearLayers();

    const allBounds = [];
    data.routes.forEach(route => {
        if (!route.route_geometry || !route.route_geometry.coordinates) return;
        
        const latlngs = route.route_geometry.coordinates.map(coord => [coord[1], coord[0]]);
        
        const polyline = L.polyline(latlngs, {
            color: route.color_hex,
            weight: 5,
            opacity: 0.9,
            lineJoin: "round"
        }).bindPopup(`<strong>${route.vehicle_name}</strong><br>Distance: ${(route.total_distance_m / 1000).toFixed(1)} km<br>Est Cost: Rs ${route.estimated_cost_inr}`);
        
        state.routesLayer.addLayer(polyline);
        latlngs.forEach(ll => allBounds.push(ll));
    });

    if (allBounds.length > 0) {
        state.map.fitBounds(allBounds, { padding: [40, 40] });
    }

    // Show Metrics Bar and Animation Toolbar
    const metricsBar = document.getElementById("mapMetricsBar");
    metricsBar.classList.remove("hidden");
    document.getElementById("metricDist").textContent = `${data.total_fleet_distance_km} km`;
    document.getElementById("metricTime").textContent = `${data.total_fleet_duration_hours} hrs`;
    document.getElementById("metricVehicles").textContent = `${data.routes.length} Active Vehicles`;

    document.getElementById("mapAnimBar").classList.remove("hidden");

    renderItineraryTab(data);

    const itineraryTabBtn = document.getElementById("itineraryTabBtn");
    itineraryTabBtn.disabled = false;
    if (autoSwitchTab) {
        itineraryTabBtn.click();
    }

    showToast(`Optimal routes calculated in ${data.solve_duration_ms} ms`, "success");
}

// Render Driver Itinerary Tab
function renderItineraryTab(data) {
    document.getElementById("summaryDistance").textContent = `${data.total_fleet_distance_km} km`;
    document.getElementById("summaryDuration").textContent = `${data.total_fleet_duration_hours} hrs`;
    document.getElementById("summaryCost").textContent = `Rs ${Math.round(data.total_fleet_cost_inr).toLocaleString()}`;
    document.getElementById("summaryVehicles").textContent = data.routes.length;

    const container = document.getElementById("routesContainer");
    let html = "";

    data.routes.forEach((r) => {
        html += `
            <div class="route-result-card" style="border-left: 4px solid ${r.color_hex};">
                <div class="route-header-box">
                    <span class="route-title">${r.vehicle_name} (${r.vehicle_class.toUpperCase()})</span>
                    <span class="route-cost">Rs ${r.estimated_cost_inr}</span>
                </div>
                <div class="route-stats-row">
                    <span>Distance: ${(r.total_distance_m / 1000).toFixed(1)} km</span>
                    <span>Time: ${(r.total_duration_s / 3600).toFixed(1)} hrs</span>
                    <span>Cargo: ${r.total_load_kg} kg</span>
                </div>
                <div class="timeline-stops">
        `;

        r.stops_visited.forEach((s, sIdx) => {
            const isDepot = sIdx === 0 || sIdx === r.stops_visited.length - 1;
            const markerText = isDepot ? "Hub" : sIdx;
            html += `
                <div class="timeline-row">
                    <span class="timeline-dot">${markerText}</span>
                    <span class="timeline-name">${s.name}</span>
                    <span class="timeline-time">${s.clock_time_str}</span>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// LIVE DRIVER ROUTE ANIMATION ON MAP
async function startRouteAnimation() {
    stopRouteAnimation();

    if (!state.currentRoutes || state.currentRoutes.length === 0) {
        showToast("Calculating optimal routes first...", "info");
        await optimizeRoutes(false);
        if (!state.currentRoutes || state.currentRoutes.length === 0) {
            showToast("Please add stops and ensure vehicles are configured.", "warning");
            return;
        }
    }

    state.isAnimating = true;
    document.getElementById("mapAnimBar").classList.remove("hidden");
    document.getElementById("startMapAnimBtn").classList.add("hidden");
    document.getElementById("stopMapAnimBtn").classList.remove("hidden");
    
    const speedMultiplier = state.animationSpeed || 1;
    document.getElementById("animStatusIndicator").textContent = `Driver Status: Moving (${state.currentRoutes.length} active vehicles @ ${speedMultiplier}x speed)`;

    state.currentRoutes.forEach((route) => {
        if (!route.route_geometry || !route.route_geometry.coordinates || route.route_geometry.coordinates.length < 2) return;

        // Raw points [lat, lon]
        const rawPoints = route.route_geometry.coordinates.map(c => [c[1], c[0]]);

        // Interpolate for smooth glide between coordinates
        const smoothPoints = [];
        for (let i = 0; i < rawPoints.length - 1; i++) {
            const p1 = rawPoints[i];
            const p2 = rawPoints[i + 1];
            smoothPoints.push(p1);
            
            // Add intermediate points
            const steps = 3;
            for (let s = 1; s < steps; s++) {
                smoothPoints.push([
                    p1[0] + (p2[0] - p1[0]) * (s / steps),
                    p1[1] + (p2[1] - p1[1]) * (s / steps)
                ]);
            }
        }
        smoothPoints.push(rawPoints[rawPoints.length - 1]);

        const isVan = route.vehicle_class === "van";
        const iconHtml = isVan ? '<i class="fa-solid fa-truck-pickup"></i>' : '<i class="fa-solid fa-truck-front"></i>';

        const vehicleIcon = L.divIcon({
            className: "sim-vehicle-icon",
            html: `<div class="animated-vehicle-dot" style="background-color: ${route.color_hex};">${iconHtml}</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12]
        });

        const marker = L.marker(smoothPoints[0], { icon: vehicleIcon }).addTo(state.map);
        marker.bindTooltip(`<strong>${route.vehicle_name}</strong><br>Status: In Transit`, {
            direction: "top",
            offset: [0, -12],
            className: "driver-map-popup"
        });

        state.animationMarkers.push(marker);

        let currentStep = 0;
        const totalSteps = smoothPoints.length;
        const baseInterval = 65;
        const speedMs = Math.max(20, Math.round(baseInterval / speedMultiplier));

        const timer = setInterval(() => {
            if (!state.isAnimating) return;
            currentStep++;
            if (currentStep >= totalSteps) {
                currentStep = 0; // Return to hub / loop route
            }
            marker.setLatLng(smoothPoints[currentStep]);
        }, speedMs);

        state.animationIntervals.push(timer);
    });

    showToast(`Driver movement simulation running at ${speedMultiplier}x speed.`, "info");
}

function stopRouteAnimation() {
    state.isAnimating = false;
    document.getElementById("startMapAnimBtn")?.classList.remove("hidden");
    document.getElementById("stopMapAnimBtn")?.classList.add("hidden");
    const indicator = document.getElementById("animStatusIndicator");
    if (indicator) indicator.textContent = "Driver Status: Paused at Depot";

    state.animationIntervals.forEach(clearInterval);
    state.animationIntervals = [];

    state.animationMarkers.forEach(m => state.map.removeLayer(m));
    state.animationMarkers = [];
}

// RUN AI SIMULATION (Preset or Custom Problem)
async function runSimulationRequest(customProblemText = null) {
    const isCustom = customProblemText !== null;
    const btn = isCustom 
        ? document.getElementById("runCustomSimulationBtn") 
        : document.getElementById("runSimulationBtn");

    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing with AI...';

    const fleet = buildFleetSpec();
    const payload = {
        scenario_type: isCustom ? "CUSTOM_SITUATION" : state.selectedScenario,
        custom_situation_text: customProblemText,
        depot: state.depot,
        fleet: fleet,
        stops: state.stops,
        departure_time_iso: "2026-10-09T08:30:00+05:30",
        parameters: {
            delay_minutes: 60,
            vehicle_id: "TRUCK-01 (Tata 407)"
        }
    };

    try {
        const res = await fetch("/api/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Simulation analysis failed");
        }

        const data = await res.json();
        renderSimulationResult(data);
    } catch (err) {
        showToast(`Error: ${err.message}`, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
    }
}

// Render Simulation Result Card
function renderSimulationResult(data) {
    const card = document.getElementById("simResultCard");
    card.classList.remove("hidden");

    const pill = document.getElementById("simStatusPill");
    if (data.feasibility_status === "VIOLATION_DETECTED") {
        pill.className = "result-badge badge-warning";
        pill.textContent = "RULE VIOLATION DETECTED";
    } else {
        pill.className = "result-badge badge-success";
        pill.textContent = "COMPLIANT / PERMITTED";
    }

    document.getElementById("simSpeedText").textContent = `${(data.simulation_duration_ms / 1000).toFixed(2)}s`;
    document.getElementById("simScenarioTitle").textContent = data.scenario_title;
    
    document.getElementById("simCostDelta").textContent = (data.cost_difference_inr >= 0 ? "+" : "") + "Rs " + Math.round(data.cost_difference_inr).toLocaleString();
    document.getElementById("simTimeDelta").textContent = (data.simulated_duration_hours - data.baseline_duration_hours >= 0 ? "+" : "") + (data.simulated_duration_hours - data.baseline_duration_hours).toFixed(1) + " hrs";
    
    const fineBox = document.getElementById("simFineRisk");
    if (data.violations && data.violations.length > 0) {
        fineBox.textContent = "Rs " + data.violations[0].penalty_fine_inr.toLocaleString();
        fineBox.className = "stat-digit text-danger";
    } else {
        fineBox.textContent = "Rs 0 (Clean)";
        fineBox.className = "stat-digit text-success";
    }

    document.getElementById("simAiReport").textContent = data.ai_advisory_recommendation;
    document.getElementById("simActionText").textContent = data.suggested_action;

    showToast("AI scenario simulation completed", "success");
}

// Toast Notifications
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    const icon = type === "success" ? "fa-circle-check" : type === "error" ? "fa-circle-xmark" : "fa-circle-info";
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 250);
    }, 3000);
}

// INITIALIZE REGULATORY MAP LAYERS
function initRegulatoryLayers() {
    // 1. Municipal No-Entry Geofence Polygon
    const geofencePolygon = L.polygon(MUMBAI_GEOFENCE_COORDS, {
        color: "#ef4444",
        weight: 2,
        dashArray: "6, 6",
        fillColor: "#ef4444",
        fillOpacity: 0.12
    }).bindPopup(`
        <div class="regulatory-popup">
            <h4><i class="fa-solid fa-ban" style="color:#ef4444"></i> Greater Mumbai No-Entry Zone</h4>
            <p><strong>Authority:</strong> Mumbai Traffic Police (Sec 115 & 116 MVA)</p>
            <p><strong>Restricted Hours:</strong> 08:00 AM - 11:30 AM & 05:00 PM - 09:30 PM</p>
            <p><strong>Restricted:</strong> Heavy Freight Trucks (Tata 407, Eicher, HCVs)</p>
            <p><strong>Exempt:</strong> Delivery Vans (Tata Ace & LCVs under 3.5T GVW)</p>
            <span class="regulatory-tag tag-geofence">Fine Risk: Rs 20,000 + Seizure</span>
        </div>
    `);
    state.geofenceLayer.addLayer(geofencePolygon);

    // 2. Height Barriers & Bridge Limits
    REGULATORY_BARRIERS.forEach(barrier => {
        if (barrier.type === "height_gantry") {
            const icon = L.divIcon({
                className: "regulatory-map-marker barrier-map-marker",
                html: `<i class="fa-solid fa-arrows-up-down"></i>`,
                iconSize: [26, 26],
                iconAnchor: [13, 13]
            });
            const marker = L.marker([barrier.lat, barrier.lon], { icon }).bindPopup(`
                <div class="regulatory-popup">
                    <h4><i class="fa-solid fa-triangle-exclamation" style="color:#f59e0b"></i> ${barrier.name}</h4>
                    <p><strong>Restriction:</strong> Height Clearance &le; ${barrier.height_limit_m} meters</p>
                    <p>${barrier.rule_details}</p>
                    <span class="regulatory-tag tag-barrier">2.5m Flyover Gantry</span>
                </div>
            `);
            state.barriersLayer.addLayer(marker);
        } else if (barrier.type === "bridge_weight") {
            const icon = L.divIcon({
                className: "regulatory-map-marker bridge-map-marker",
                html: `<i class="fa-solid fa-weight-hanging"></i>`,
                iconSize: [26, 26],
                iconAnchor: [13, 13]
            });
            const marker = L.marker([barrier.lat, barrier.lon], { icon }).bindPopup(`
                <div class="regulatory-popup">
                    <h4><i class="fa-solid fa-triangle-exclamation" style="color:#ea580c"></i> ${barrier.name}</h4>
                    <p><strong>Restriction:</strong> Gross Vehicle Weight &le; ${barrier.weight_limit_t} Tonnes</p>
                    <p>${barrier.rule_details}</p>
                    <span class="regulatory-tag tag-bridge">7.5T Bridge Limit</span>
                </div>
            `);
            state.bridgesLayer.addLayer(marker);
        }
    });

    // Layer Toggle Event Listeners
    document.getElementById("toggleGeofence")?.addEventListener("change", (e) => {
        if (e.target.checked) {
            state.map.addLayer(state.geofenceLayer);
        } else {
            state.map.removeLayer(state.geofenceLayer);
        }
    });

    document.getElementById("toggleBarriers")?.addEventListener("change", (e) => {
        if (e.target.checked) {
            state.map.addLayer(state.barriersLayer);
        } else {
            state.map.removeLayer(state.barriersLayer);
        }
    });

    document.getElementById("toggleBridges")?.addEventListener("change", (e) => {
        if (e.target.checked) {
            state.map.addLayer(state.bridgesLayer);
        } else {
            state.map.removeLayer(state.bridgesLayer);
        }
    });
}

// RENDER COMMERCIAL DISPATCH MANIFEST MODAL
function renderManifestModal(data) {
    const serial = `MANIFEST-MMRDA-${Date.now().toString().slice(-6)}`;
    document.getElementById("manifestSerialId").textContent = serial;

    const departureClock = document.getElementById("clockDisplay")?.textContent || "08:30 AM";
    const container = document.getElementById("manifestContent");

    let html = `
        <div class="manifest-header-block">
            <div class="manifest-meta-col">
                <strong>RouteOpt Commercial Fleet Dispatch Manifest</strong>
                <span>Region: Mumbai Metropolitan Region (MMRDA / Police Traffic Branch)</span>
                <span>Operating Hub: ${state.depot?.name || "Bhiwandi Central Freight Hub"}</span>
            </div>
            <div class="manifest-meta-col" style="text-align: right;">
                <div class="manifest-badge-legal">
                    <i class="fa-solid fa-shield-check"></i> Regulatory Clearance Verified
                </div>
                <div style="margin-top: 4px; color: #94a3b8; font-size: 11px;">
                    Shift Departure: <strong>${departureClock}</strong>
                </div>
            </div>
        </div>

        <div class="summary-stat-grid" style="margin-bottom: 16px;">
            <div class="stat-cell">
                <span class="stat-name">Active Vehicles</span>
                <span class="stat-digit">${data.routes.length}</span>
            </div>
            <div class="stat-cell">
                <span class="stat-name">Total Fleet Distance</span>
                <span class="stat-digit">${data.total_fleet_distance_km} km</span>
            </div>
            <div class="stat-cell">
                <span class="stat-name">Estimated Shift Duration</span>
                <span class="stat-digit">${data.total_fleet_duration_hours} hrs</span>
            </div>
            <div class="stat-cell">
                <span class="stat-name">Estimated Operational Cost</span>
                <span class="stat-digit">Rs ${Math.round(data.total_fleet_cost_inr).toLocaleString()}</span>
            </div>
        </div>
    `;

    data.routes.forEach((route, idx) => {
        const isVan = route.vehicle_class === "van";
        const classTitle = isVan ? "Delivery Van (LCV - Tata Ace)" : "Freight Truck (MCV/HCV - Tata 407)";
        const loadKg = route.total_load_kg || 0;
        const capacityKg = isVan ? 1200 : 4500;
        const utilPct = Math.round((loadKg / capacityKg) * 100);

        html += `
            <div class="manifest-section-title">
                <i class="fa-solid fa-truck" style="color:${route.color_hex}"></i>
                Vehicle ${idx + 1}: ${route.vehicle_name} (${classTitle})
                <span style="margin-left: auto; font-size: 11px; font-weight: normal; color: #94a3b8;">
                    Load: ${loadKg} kg / ${capacityKg} kg (${utilPct}% Capacity) | Est. Cost: Rs ${Math.round(route.estimated_cost_inr).toLocaleString()}
                </span>
            </div>

            <table class="manifest-table">
                <thead>
                    <tr>
                        <th style="width: 35px;">#</th>
                        <th>Stop / Waypoint Location</th>
                        <th style="width: 85px;">Arrival</th>
                        <th style="width: 70px;">Dwell</th>
                        <th style="width: 85px;">Drop Load</th>
                        <th style="width: 85px;">Remaining</th>
                        <th style="width: 120px;">Compliance</th>
                    </tr>
                </thead>
                <tbody>
        `;

        (route.stops_visited || []).forEach((stop, sIdx) => {
            const isDepot = sIdx === 0 || sIdx === route.stops_visited.length - 1;
            const dropKg = isDepot ? "-" : `${stop.current_load_kg || 0} kg`;
            html += `
                <tr>
                    <td>${sIdx + 1}</td>
                    <td><strong>${stop.name}</strong></td>
                    <td>${stop.clock_time_str || "-"}</td>
                    <td>${isDepot ? "Hub Start" : `${Math.round(stop.waiting_time_sec / 60) || 5} min`}</td>
                    <td>${dropKg}</td>
                    <td>${stop.current_load_kg} kg</td>
                    <td><span style="color: #4ade80;"><i class="fa-solid fa-check"></i> Compliant</span></td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;
    });

    html += `
        <div class="manifest-signatures">
            <div class="sig-box">
                Driver Signature / Registration
            </div>
            <div class="sig-box">
                Transport Supervisor Sign-Off
            </div>
            <div class="sig-box">
                Regional Gate Clearance Stamp
            </div>
        </div>
    `;

    container.innerHTML = html;
}

// DOWNLOAD DISPATCH MANIFEST CSV
function downloadManifestCsv() {
    if (!state.lastOptimizationData || !state.lastOptimizationData.routes) {
        showToast("No active route manifest data to export.", "warning");
        return;
    }

    const headers = ["Vehicle ID", "Vehicle Name", "Class", "Stop Seq", "Stop Name", "Arrival Clock Time", "Drop Demand Kg", "Total Load Kg"];
    const rows = [headers.join(",")];

    state.lastOptimizationData.routes.forEach(route => {
        (route.stops_visited || []).forEach((stop, idx) => {
            const cleanName = `"${stop.name.replace(/"/g, '""')}"`;
            rows.push([
                route.vehicle_id,
                `"${route.vehicle_name}"`,
                route.vehicle_class,
                idx + 1,
                cleanName,
                stop.clock_time_str || "",
                stop.current_load_kg || 0,
                route.total_load_kg || 0
            ].join(","));
        });
    });

    const csvContent = rows.join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `RouteOpt_Dispatch_Manifest_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast("Downloaded Dispatch Manifest CSV.", "success");
}

