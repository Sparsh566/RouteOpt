/**
 * RouteOpt - Commercial Fleet Routing & AI What-If Simulator (v2 & v3)
 * Full Client Implementation
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
    routesLayer: null
};

// Preset Mumbai Logistics Dataset
const MUMBAI_PRESET = {
    depot: {
        depot_id: "DEPOT-BHIWANDI",
        name: "Bhiwandi Freight Logistics Hub (Outer Ring)",
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
            name: "Thane West Distribution Center",
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
    
    // Auto-load Mumbai dataset for immediate demo readiness
    loadMumbaiPreset();
});

// Initialize Leaflet Map
function initMap() {
    state.map = L.map("map", {
        center: [19.1200, 72.9500],
        zoom: 11,
        zoomControl: false
    });

    L.control.zoom({ position: "bottomright" }).addTo(state.map);

    // Dark-styled tiles
    L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 19,
        subdomains: "abcd"
    }).addTo(state.map);

    state.markersLayer = L.layerGroup().addTo(state.map);
    state.routesLayer = L.layerGroup().addTo(state.map);

    // Map click to place custom stops
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

    // Shift Time Slider
    const slider = document.getElementById("shiftTimeSlider");
    slider.addEventListener("input", (e) => {
        state.departureHour = parseFloat(e.target.value);
        updateClockDisplay(state.departureHour);
    });

    // Fleet Counters
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

    // Scenario Selectors
    document.querySelectorAll(".scenario-option").forEach(opt => {
        opt.addEventListener("click", () => {
            document.querySelectorAll(".scenario-option").forEach(o => {
                o.classList.remove("active");
                o.querySelector(".scenario-radio i").className = "fa-regular fa-circle";
            });
            opt.classList.add("active");
            opt.querySelector(".scenario-radio i").className = "fa-solid fa-circle-dot";
            state.selectedScenario = opt.dataset.scenario;
        });
    });

    // Run AI Simulation Button
    document.getElementById("runSimulationBtn").addEventListener("click", runAiSimulation);
}

// Update Clock Display & Municipal No-Entry Indicator
function updateClockDisplay(hourVal) {
    const hours = Math.floor(hourVal);
    const mins = (hourVal % 1) * 60;
    const ampm = hours >= 12 ? "PM" : "AM";
    const displayHour = hours % 12 === 0 ? 12 : hours % 12;
    const timeStr = `${String(displayHour).padStart(2, "0")}:${String(mins).padStart(2, "0")} ${ampm} IST`;
    
    document.getElementById("clockDisplay").textContent = timeStr;

    // Check No-Entry Status:
    // Morning peak: 08:00 - 11:30 (8.0 - 11.5)
    // Evening peak: 17:00 - 21:30 (17.0 - 21.5)
    const indicator = document.getElementById("noEntryIndicator");
    const dot = indicator.querySelector(".indicator-dot");
    const text = document.getElementById("indicatorText");

    if (hourVal >= 8.0 && hourVal <= 11.5) {
        dot.className = "indicator-dot red";
        text.textContent = "Morning Peak HCV Ban Active (08:00 - 11:30 AM)";
    } else if (hourVal >= 17.0 && hourVal <= 21.5) {
        dot.className = "indicator-dot red";
        text.textContent = "Evening Peak Severe HCV Ban Active (05:00 - 09:30 PM)";
    } else {
        dot.className = "indicator-dot green";
        text.textContent = "All Urban Corridors Unrestricted for Vans & Trucks";
    }
}

// Update Fleet Summary Pill
function updateFleetSummary() {
    const badge = document.getElementById("fleetSummaryBadge");
    badge.textContent = `${state.fleet.vans} Vans | ${state.fleet.trucks} Trucks`;
    
    // Enable optimize button if at least 1 vehicle and at least 1 stop
    const optimizeBtn = document.getElementById("optimizeBtn");
    const hasVehicles = (state.fleet.vans + state.fleet.trucks) > 0;
    const hasStops = state.stops.length > 0 && state.depot !== null;
    optimizeBtn.disabled = !(hasVehicles && hasStops);
}

// Load Mumbai Logistics Preset
function loadMumbaiPreset() {
    state.depot = { ...MUMBAI_PRESET.depot };
    state.stops = JSON.parse(JSON.stringify(MUMBAI_PRESET.stops));
    renderLocationsList();
    renderMapMarkers();
    updateFleetSummary();
    showToast("Loaded Mumbai Commercial Logistics dataset (Bhiwandi Hub & 6 Drops)", "success");
}

// Clear All Stops
function clearAll() {
    state.depot = null;
    state.stops = [];
    state.currentRoutes = [];
    state.markersLayer.clearLayers();
    state.routesLayer.clearLayers();
    renderLocationsList();
    updateFleetSummary();
    document.getElementById("routesTabBtn").disabled = true;
    document.getElementById("mapMetricsBar").classList.add("hidden");
    showToast("Reset all locations and routes", "warning");
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
        showToast("Set Logistics Hub (Depot)", "success");
    } else {
        const idx = state.stops.length + 1;
        state.stops.push({
            stop_id: `STOP-${String(idx).padStart(2, "0")}`,
            name: `Commercial Drop ${idx}`,
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
            <div class="empty-list-state">
                <i class="fa-solid fa-map-location-dot"></i>
                <p>No freight points loaded</p>
                <button class="btn btn-secondary btn-sm" id="loadSampleBtnInline">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Load Mumbai Freight Dataset
                </button>
            </div>
        `;
        document.getElementById("loadSampleBtnInline")?.addEventListener("click", loadMumbaiPreset);
        stopsCount.textContent = "0 stops";
        return;
    }

    stopsCount.textContent = `${state.stops.length} stops`;
    let html = "";

    if (state.depot) {
        html += `
            <div class="location-item depot-item">
                <div class="location-badge depot-badge"><i class="fa-solid fa-warehouse"></i></div>
                <div class="location-details">
                    <div class="location-title">${state.depot.name}</div>
                    <div class="location-sub">Origin Distribution Center &bull; Central Hub</div>
                </div>
            </div>
        `;
    }

    state.stops.forEach((s, i) => {
        const zoneBadge = s.is_in_restricted_urban_core 
            ? '<span class="tag-orange">Restricted Urban Core</span>' 
            : '<span class="tag-green">Peripheral Arterial</span>';
        
        html += `
            <div class="location-item">
                <div class="location-badge stop-badge">${i + 1}</div>
                <div class="location-details">
                    <div class="location-title">${s.name}</div>
                    <div class="location-sub">
                        <span><i class="fa-solid fa-box"></i> ${s.demand_kg} kg</span> &bull; 
                        <span><i class="fa-solid fa-stopwatch"></i> ${Math.round(s.service_duration_sec / 60)}m unload</span>
                    </div>
                    <div class="location-tags-row">${zoneBadge}</div>
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
            html: `<div style="background:#2563eb; color:#fff; width:34px; height:34px; border-radius:50%; display:flex; align-items:center; justify-content:center; box-shadow:0 0 14px rgba(37,99,235,0.7); border:2px solid #fff;"><i class="fa-solid fa-warehouse"></i></div>`,
            iconSize: [34, 34],
            iconAnchor: [17, 17]
        });
        const marker = L.marker([state.depot.lat, state.depot.lon], { icon: depotIcon })
            .bindPopup(`<strong>${state.depot.name}</strong><br>Central Logistics Hub`);
        state.markersLayer.addLayer(marker);
        bounds.push([state.depot.lat, state.depot.lon]);
    }

    state.stops.forEach((s, i) => {
        const stopIcon = L.divIcon({
            className: "custom-stop-marker",
            html: `<div style="background:#0f172a; color:#38bdf8; width:28px; height:28px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:12px; border:2px solid #38bdf8; box-shadow:0 0 8px rgba(56,189,248,0.5);">${i + 1}</div>`,
            iconSize: [28, 28],
            iconAnchor: [14, 14]
        });
        const marker = L.marker([s.lat, s.lon], { icon: stopIcon })
            .bindPopup(`<strong>#${i + 1} ${s.name}</strong><br>Demand: ${s.demand_kg} kg<br>Zone: ${s.is_in_restricted_urban_core ? "Restricted Urban Core" : "Peripheral Road"}`);
        state.markersLayer.addLayer(marker);
        bounds.push([s.lat, s.lon]);
    });

    if (bounds.length > 0) {
        state.map.fitBounds(bounds, { padding: [50, 50] });
    }
}

// Build Fleet Configuration Array
function buildFleetSpec() {
    const fleet = [];
    for (let i = 0; i < state.fleet.vans; i++) {
        fleet.push({
            vehicle_id: `VAN-${String(i + 1).padStart(2, "0")}`,
            name: `Tata Ace Delivery Van #${i + 1}`,
            vehicle_class: "van",
            gross_vehicle_weight_tonnes: 2.2,
            height_meters: 1.9,
            payload_capacity_kg: 1200.0,
            fixed_dispatch_cost: 250.0,
            running_cost_per_km: 12.0,
            color_hex: "#06b6d4" // Vibrant Cyan
        });
    }
    for (let i = 0; i < state.fleet.trucks; i++) {
        fleet.push({
            vehicle_id: `TRUCK-${String(i + 1).padStart(2, "0")}`,
            name: `Tata 407 Freight Truck #${i + 1}`,
            vehicle_class: "truck",
            gross_vehicle_weight_tonnes: 7.2,
            height_meters: 3.1,
            payload_capacity_kg: 4500.0,
            fixed_dispatch_cost: 600.0,
            running_cost_per_km: 22.0,
            color_hex: "#f59e0b" // Vibrant Amber
        });
    }
    return fleet;
}

// Optimize Commercial Fleet Routes
async function optimizeRoutes() {
    const btn = document.getElementById("optimizeBtn");
    const btnText = document.getElementById("optimizeBtnText");
    btn.disabled = true;
    btnText.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Solving CVRPTW...';

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
            throw new Error(err.detail || "Optimization failed");
        }

        const data = await res.json();
        handleOptimizationSuccess(data);
    } catch (err) {
        showToast(`Optimization Error: ${err.message}`, "error");
    } finally {
        btn.disabled = false;
        btnText.innerHTML = '<i class="fa-solid fa-bolt"></i> Optimize Commercial Fleet';
    }
}

// Handle Optimization Success
function handleOptimizationSuccess(data) {
    state.currentRoutes = data.routes;
    state.routesLayer.clearLayers();

    // Render Routes on Leaflet Map
    const allBounds = [];
    data.routes.forEach(route => {
        if (!route.route_geometry || !route.route_geometry.coordinates) return;
        
        // GeoJSON coordinates are [lon, lat], Leaflet expects [lat, lon]
        const latlngs = route.route_geometry.coordinates.map(coord => [coord[1], coord[0]]);
        
        const polyline = L.polyline(latlngs, {
            color: route.color_hex,
            weight: 5,
            opacity: 0.85,
            lineJoin: "round"
        }).bindPopup(`<strong>${route.vehicle_name}</strong><br>Class: ${route.vehicle_class.toUpperCase()}<br>Distance: ${(route.total_distance_m / 1000).toFixed(1)} km<br>Est Cost: ₹${route.estimated_cost_inr}`);
        
        state.routesLayer.addLayer(polyline);
        latlngs.forEach(ll => allBounds.push(ll));
    });

    if (allBounds.length > 0) {
        state.map.fitBounds(allBounds, { padding: [50, 50] });
    }

    // Update Floating Metrics Bar
    const metricsBar = document.getElementById("mapMetricsBar");
    metricsBar.classList.remove("hidden");
    document.getElementById("metricDist").textContent = `${data.total_fleet_distance_km} km`;
    document.getElementById("metricTime").textContent = `${data.total_fleet_duration_hours} hrs`;
    document.getElementById("metricVehicles").textContent = `${data.routes.length} Active Vehicles`;

    // Render Routes Tab
    renderRoutesTab(data);

    // Switch to Routes Tab
    const routesTabBtn = document.getElementById("routesTabBtn");
    routesTabBtn.disabled = false;
    routesTabBtn.click();

    showToast(`Optimal fleet plan generated (${data.solve_duration_ms} ms)`, "success");
}

// Render Solved Routes Itinerary Tab
function renderRoutesTab(data) {
    document.getElementById("summaryDistance").textContent = `${data.total_fleet_distance_km} km`;
    document.getElementById("summaryDuration").textContent = `${data.total_fleet_duration_hours} hrs`;
    document.getElementById("summaryCost").textContent = `₹${Math.round(data.total_fleet_cost_inr).toLocaleString()}`;
    document.getElementById("summaryVehicles").textContent = data.routes.length;

    const container = document.getElementById("routesContainer");
    let html = "";

    data.routes.forEach((r, idx) => {
        const isVan = r.vehicle_class === "van";
        const iconClass = isVan ? "fa-van-shuttle" : "fa-truck";
        
        html += `
            <div class="card route-result-card" style="border-left: 4px solid ${r.color_hex};">
                <div class="route-header">
                    <div class="route-title-box">
                        <i class="fa-solid ${iconClass}" style="color: ${r.color_hex}; font-size: 18px;"></i>
                        <div>
                            <h4>${r.vehicle_name}</h4>
                            <span class="route-sub">${r.vehicle_class.toUpperCase()} &bull; Total Cargo: ${r.total_load_kg} kg</span>
                        </div>
                    </div>
                    <span class="badge" style="background: rgba(255,255,255,0.1); color: ${r.color_hex};">₹${r.estimated_cost_inr}</span>
                </div>

                <div class="route-quick-stats">
                    <span><i class="fa-solid fa-road"></i> ${(r.total_distance_m / 1000).toFixed(1)} km</span>
                    <span><i class="fa-solid fa-clock"></i> ${(r.total_duration_s / 3600).toFixed(1)} hrs</span>
                    <span><i class="fa-solid fa-location-dot"></i> ${r.stops_visited.length - 2} drops</span>
                </div>

                <div class="stop-timeline">
        `;

        r.stops_visited.forEach((s, sIdx) => {
            const isDepot = sIdx === 0 || sIdx === r.stops_visited.length - 1;
            const markerIcon = isDepot ? '<i class="fa-solid fa-warehouse"></i>' : sIdx;
            
            html += `
                <div class="timeline-stop-row">
                    <div class="stop-num">${markerIcon}</div>
                    <div class="stop-desc">
                        <strong>${s.name}</strong>
                        <span class="stop-time"><i class="fa-regular fa-clock"></i> Arrival: ${s.clock_time_str}</span>
                    </div>
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

// Run AI "What-If" Simulation
async function runAiSimulation() {
    const btn = document.getElementById("runSimulationBtn");
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Simulating via Groq / Grok LLM...';

    const fleet = buildFleetSpec();
    const payload = {
        scenario_type: state.selectedScenario,
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
            throw new Error(err.detail || "Simulation failed");
        }

        const data = await res.json();
        renderSimulationResult(data);
    } catch (err) {
        showToast(`Simulation Error: ${err.message}`, "error");
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Run AI What-If Simulation';
    }
}

// Render AI Simulation Results Card
function renderSimulationResult(data) {
    const card = document.getElementById("simResultCard");
    card.classList.remove("hidden");

    // Pill
    const pill = document.getElementById("simStatusPill");
    if (data.feasibility_status === "VIOLATION_DETECTED") {
        pill.className = "status-pill status-violation";
        pill.textContent = "VIOLATION DETECTED";
    } else {
        pill.className = "status-pill status-compliant";
        pill.textContent = "COMPLIANT / RE-ROUTED";
    }

    document.getElementById("simSpeedText").textContent = `${(data.simulation_duration_ms / 1000).toFixed(2)}s`;
    document.getElementById("simScenarioTitle").textContent = data.scenario_title;
    
    document.getElementById("simCostDelta").textContent = (data.cost_difference_inr >= 0 ? "+" : "") + "₹" + Math.round(data.cost_difference_inr).toLocaleString();
    document.getElementById("simTimeDelta").textContent = (data.simulated_duration_hours - data.baseline_duration_hours >= 0 ? "+" : "") + (data.simulated_duration_hours - data.baseline_duration_hours).toFixed(1) + " hrs";
    
    const fineBox = document.getElementById("simFineRisk");
    if (data.violations && data.violations.length > 0) {
        fineBox.textContent = "₹" + data.violations[0].penalty_fine_inr.toLocaleString();
        fineBox.className = "text-danger";
    } else {
        fineBox.textContent = "₹0 (Clean)";
        fineBox.className = "text-success";
    }

    document.getElementById("simAiReport").textContent = data.ai_advisory_recommendation;
    document.getElementById("simActionText").textContent = data.suggested_action;
    document.getElementById("aiEngineBadge").textContent = data.llm_engine_used;

    showToast("AI Scenario Simulation completed", "success");
}

// Toast Notifications
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    
    const icon = type === "success" ? "fa-circle-check" : type === "error" ? "fa-triangle-exclamation" : "fa-circle-info";
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3200);
}
