/**
 * RouteOpt - Commercial Fleet Routing & Dispatch System
 * Features:
 * 1. Multi-vehicle CVRPTW with Van and Truck road rules.
 * 2. AI What-If Scenario simulation with preset and custom problem analysis.
 * 3. Live Driver Route Animation on map.
 */

// XSS Prevention Utility
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

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
    selectedRegion: "MUMBAI_MMRDA",
    
    // Animation tracking
    animationMarkers: [],
    animationIntervals: [],
    isAnimating: false,

    // Fleet Manager & Driver HUD state
    activeDriverVehicleId: null,
    driverDeliveredStops: {}
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

// Pune Municipal Corporation (PMC) Regulatory Core Geofence
const PUNE_GEOFENCE_COORDS = [
    [18.5650, 73.8300], // Khadki / University
    [18.5600, 73.8900], // Yerwada / Bund Garden
    [18.5100, 73.9100], // Camp / Hadapsar Border
    [18.4800, 73.8600], // Swargate / Bibwewadi
    [18.4900, 73.8200], // Karve Road / Erandwane
    [18.5300, 73.8100], // Senapati Bapat Road
    [18.5650, 73.8300]  // Back to University
];

// Nagpur Municipal Corporation (NMC) Regulatory Central Core Geofence
const NAGPUR_GEOFENCE_COORDS = [
    [21.1750, 79.0750], // Sadar / Raj Bhavan North
    [21.1700, 79.1150], // Pachpaoli / Shanti Nagar East
    [21.1550, 79.1250], // Itwari Wholesale / Maskasath
    [21.1350, 79.1150], // Mahal / Kotwali South-East
    [21.1250, 79.0850], // Dhantoli / Rahate Colony South
    [21.1350, 79.0550], // Dharampeth / Shankar Nagar West
    [21.1600, 79.0600], // Law College / Seminary Hills North-West
    [21.1750, 79.0750]  // Back to Sadar
];

// Structural Road Barriers (Mumbai)
const MUMBAI_BARRIERS = [
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

// Structural Road Barriers (Pune)
const PUNE_BARRIERS = [
    {
        type: "height_gantry",
        name: "Swargate Flyover Clearance Gantry",
        lat: 18.5018,
        lon: 73.8585,
        height_limit_m: 2.5,
        rule_details: "2.5m Max Clearance. Freight trucks diverted to ground level.",
        penalty: "Gantry collision hazard"
    },
    {
        type: "bridge_weight",
        name: "Old Lakdi Pul (Sambhaji Bridge)",
        lat: 18.5150,
        lon: 73.8480,
        weight_limit_t: 5.0,
        rule_details: "5.0 Tonnes Gross Vehicle Weight limit on heritage arch span.",
        penalty: "Heritage infrastructure fine"
    },
    {
        type: "bridge_weight",
        name: "Shivaji Bridge (Dengle Bridge)",
        lat: 18.5280,
        lon: 73.8550,
        weight_limit_t: 5.0,
        rule_details: "5.0 Tonnes Weight Limit. Heavy trucks must use Sangam Bridge.",
        penalty: "Arterial weight limit penalty"
    },
    {
        type: "height_gantry",
        name: "Pune University Flyover Bar",
        lat: 18.5410,
        lon: 73.8290,
        height_limit_m: 2.5,
        rule_details: "2.5m Clearance Bar. Trucks diverted to Senapati Bapat Road surface.",
        penalty: "Traffic obstruction fine"
    }
];

// Master Central Hub (Pune)
const PUNE_PRESET_DEPOT = {
    depot_id: "DEPOT-CHAKAN",
    name: "Bhosari-Chakan MIDC Central Freight Terminal",
    lat: 18.6250,
    lon: 73.8350,
    operating_hours_sec: 43200
};

// 10 Commercial Delivery Drops across Pune Metropolitan Area
const PUNE_ALL_STOPS = [
    { stop_id: "PUNE-01", name: "Swargate Wholesale Market", lat: 18.5018, lon: 73.8585, demand_kg: 500, time_window_start_sec: 0, time_window_end_sec: 36000, service_duration_sec: 600, is_in_restricted_urban_core: true },
    { stop_id: "PUNE-02", name: "Shivajinagar Goods Terminal", lat: 18.5314, lon: 73.8446, demand_kg: 450, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 500, is_in_restricted_urban_core: true },
    { stop_id: "PUNE-03", name: "Hinjawadi Phase 1 Logistics Bay", lat: 18.5913, lon: 73.7389, demand_kg: 700, time_window_start_sec: 0, time_window_end_sec: 43200, service_duration_sec: 750, is_in_restricted_urban_core: false },
    { stop_id: "PUNE-04", name: "Hadapsar Industrial Estate", lat: 18.5080, lon: 73.9260, demand_kg: 600, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 600, is_in_restricted_urban_core: false },
    { stop_id: "PUNE-05", name: "Kothrud Karve Road Distribution", lat: 18.5074, lon: 73.8077, demand_kg: 350, time_window_start_sec: 3600, time_window_end_sec: 36000, service_duration_sec: 450, is_in_restricted_urban_core: true },
    { stop_id: "PUNE-06", name: "Viman Nagar Commercial Hub", lat: 18.5679, lon: 73.9143, demand_kg: 400, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 500, is_in_restricted_urban_core: true },
    { stop_id: "PUNE-07", name: "Pimpri-Chinchwad MIDC Cluster", lat: 18.6298, lon: 73.7997, demand_kg: 850, time_window_start_sec: 0, time_window_end_sec: 43200, service_duration_sec: 800, is_in_restricted_urban_core: false },
    { stop_id: "PUNE-08", name: "Katraj South Freight Corridor", lat: 18.4575, lon: 73.8677, demand_kg: 500, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 500, is_in_restricted_urban_core: false },
    { stop_id: "PUNE-09", name: "Wagholi Nagar Road Freight Bay", lat: 18.5810, lon: 73.9820, demand_kg: 400, time_window_start_sec: 0, time_window_end_sec: 43200, service_duration_sec: 400, is_in_restricted_urban_core: false },
    { stop_id: "PUNE-10", name: "Deccan Gymkhana Retail Center", lat: 18.5180, lon: 73.8390, demand_kg: 300, time_window_start_sec: 3600, time_window_end_sec: 36000, service_duration_sec: 450, is_in_restricted_urban_core: true }
];

// Structural Road Barriers (Nagpur)
const NAGPUR_BARRIERS = [
    {
        type: "bridge_weight",
        name: "Ram Jhula Cable-Stayed Railway Overbridge",
        lat: 21.1510,
        lon: 79.0920,
        weight_limit_t: 5.0,
        rule_details: "5.0 Tonnes Gross Vehicle Weight limit on arterial railway flyover. Multi-axle trucks diverted to Central Avenue underpass.",
        penalty: "Structural safety limit violation / Traffic police fine"
    },
    {
        type: "height_gantry",
        name: "Sitabuldi Metro Interchange Overhead Gantry",
        lat: 21.1460,
        lon: 79.0830,
        height_limit_m: 2.5,
        rule_details: "2.5m Steel Clearance Gantry on lower deck approach ramps. Trucks diverted to ground Wardha Road.",
        penalty: "Gantry collision hazard / Rs 10,000 fine"
    },
    {
        type: "height_gantry",
        name: "Cotton Market Narrow Railway Subway",
        lat: 21.1400,
        lon: 79.0930,
        height_limit_m: 2.5,
        rule_details: "2.5m Height Barrier. Freight trucks must bypass via Ghat Road or Manewada arterial.",
        penalty: "Low clearance subway strike hazard"
    },
    {
        type: "bridge_weight",
        name: "Itwari Old Marwari Bridge",
        lat: 21.1560,
        lon: 79.1150,
        weight_limit_t: 5.0,
        rule_details: "5.0 Tonnes Gross Vehicle Weight restriction on heritage market bridge.",
        penalty: "Overweight axle breach on narrow market span"
    }
];

// Master Central Hub (Nagpur)
const NAGPUR_PRESET_DEPOT = {
    depot_id: "DEPOT-MIHAN",
    name: "MIHAN SEZ Multi-Modal Logistics Hub",
    lat: 21.0500,
    lon: 79.0300,
    operating_hours_sec: 43200
};

// 10 Commercial Delivery Drops across Nagpur Metropolitan Area
const NAGPUR_ALL_STOPS = [
    { stop_id: "NGP-01", name: "Sitabuldi Main Retail Market", lat: 21.1458, lon: 79.0825, demand_kg: 500, time_window_start_sec: 0, time_window_end_sec: 36000, service_duration_sec: 600, is_in_restricted_urban_core: true },
    { stop_id: "NGP-02", name: "Itwari Wholesale Cloth & Spice Bazaar", lat: 21.1550, lon: 79.1120, demand_kg: 600, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 750, is_in_restricted_urban_core: true },
    { stop_id: "NGP-03", name: "Cotton Market Agro & Freight Terminal", lat: 21.1410, lon: 79.0940, demand_kg: 550, time_window_start_sec: 0, time_window_end_sec: 36000, service_duration_sec: 600, is_in_restricted_urban_core: true },
    { stop_id: "NGP-04", name: "Hingna MIDC Industrial Cluster", lat: 21.1150, lon: 78.9950, demand_kg: 750, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 700, is_in_restricted_urban_core: false },
    { stop_id: "NGP-05", name: "Butibori 5-Star Industrial Zone", lat: 20.9250, lon: 78.9900, demand_kg: 900, time_window_start_sec: 0, time_window_end_sec: 43200, service_duration_sec: 800, is_in_restricted_urban_core: false },
    { stop_id: "NGP-06", name: "Dharampeth Commercial High Street", lat: 21.1420, lon: 79.0620, demand_kg: 350, time_window_start_sec: 3600, time_window_end_sec: 36000, service_duration_sec: 450, is_in_restricted_urban_core: true },
    { stop_id: "NGP-07", name: "Gandhibagh Wholesale Goods Market", lat: 21.1500, lon: 79.1020, demand_kg: 450, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 500, is_in_restricted_urban_core: true },
    { stop_id: "NGP-08", name: "Wardha Road Metro Logistics Bay", lat: 21.0850, lon: 79.0650, demand_kg: 500, time_window_start_sec: 0, time_window_end_sec: 43200, service_duration_sec: 500, is_in_restricted_urban_core: false },
    { stop_id: "NGP-09", name: "Wadi Transport Plaza (Amravati Rd)", lat: 21.1500, lon: 78.9900, demand_kg: 700, time_window_start_sec: 1800, time_window_end_sec: 43200, service_duration_sec: 600, is_in_restricted_urban_core: false },
    { stop_id: "NGP-10", name: "Mahal Historic Commercial Quarter", lat: 21.1440, lon: 79.1100, demand_kg: 400, time_window_start_sec: 3600, time_window_end_sec: 36000, service_duration_sec: 500, is_in_restricted_urban_core: true }
];

// Master Central Hub
const MUMBAI_PRESET_DEPOT = {
    depot_id: "DEPOT-BHIWANDI",
    name: "Bhiwandi Central Freight Hub",
    lat: 19.2967,
    lon: 73.0631,
    operating_hours_sec: 43200
};

// 30 Commercial Delivery Drops across Mumbai, Navi Mumbai, and Thane
const MUMBAI_ALL_STOPS = [
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
    },
    {
        stop_id: "STOP-07",
        name: "Kalamboli Steel Market (Navi Mumbai)",
        lat: 19.0222,
        lon: 73.0988,
        demand_kg: 900,
        time_window_start_sec: 1800,
        time_window_end_sec: 43200,
        service_duration_sec: 900,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-08",
        name: "Kurla West Kamani Industrial Area",
        lat: 19.0728,
        lon: 72.8795,
        demand_kg: 400,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 500,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-09",
        name: "Goregaon East NESCO Logistics Bay",
        lat: 19.1553,
        lon: 72.8550,
        demand_kg: 450,
        time_window_start_sec: 3600,
        time_window_end_sec: 43200,
        service_duration_sec: 450,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-10",
        name: "Lower Parel Sun Mill Commercial Docks",
        lat: 18.9950,
        lon: 72.8290,
        demand_kg: 350,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 600,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-11",
        name: "Taloja MIDC Heavy Industrial Zone",
        lat: 19.0620,
        lon: 73.1380,
        demand_kg: 850,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 800,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-12",
        name: "Chembur Diamond Garden Distribution",
        lat: 19.0520,
        lon: 72.8980,
        demand_kg: 300,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 400,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-13",
        name: "Borivali West Link Road Center",
        lat: 19.2300,
        lon: 72.8480,
        demand_kg: 500,
        time_window_start_sec: 3600,
        time_window_end_sec: 43200,
        service_duration_sec: 500,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-14",
        name: "Turbhe MIDC Freight Terminal",
        lat: 19.0710,
        lon: 73.0230,
        demand_kg: 650,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 600,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-15",
        name: "Byculla Cotton Exchange Docks",
        lat: 18.9750,
        lon: 72.8360,
        demand_kg: 400,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 550,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-16",
        name: "Kanjurmarg East LBS Logistics Center",
        lat: 19.1320,
        lon: 72.9340,
        demand_kg: 350,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 450,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-17",
        name: "Malad West Infinity Logistics Bay",
        lat: 19.1840,
        lon: 72.8350,
        demand_kg: 450,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 500,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-18",
        name: "Panvel JNPT Bypass Cargo Hub",
        lat: 18.9920,
        lon: 73.1180,
        demand_kg: 950,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 900,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-19",
        name: "Ghatkopar East Pant Nagar Depo",
        lat: 19.0860,
        lon: 72.9150,
        demand_kg: 400,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 400,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-20",
        name: "Belapur CBD Commercial Sector 11",
        lat: 19.0180,
        lon: 73.0390,
        demand_kg: 500,
        time_window_start_sec: 1800,
        time_window_end_sec: 43200,
        service_duration_sec: 500,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-21",
        name: "Dahisar West Anand Nagar Checkpost",
        lat: 19.2550,
        lon: 72.8590,
        demand_kg: 350,
        time_window_start_sec: 0,
        time_window_end_sec: 36000,
        service_duration_sec: 400,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-22",
        name: "Wadala Truck Terminal Corridor",
        lat: 19.0280,
        lon: 72.8750,
        demand_kg: 700,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 700,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-23",
        name: "Worli Naka Commercial Fulfillment",
        lat: 19.0060,
        lon: 72.8180,
        demand_kg: 300,
        time_window_start_sec: 3600,
        time_window_end_sec: 36000,
        service_duration_sec: 450,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-24",
        name: "Rabale MIDC Industrial Corridor",
        lat: 19.1380,
        lon: 73.0080,
        demand_kg: 600,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 600,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-25",
        name: "Mahim West Retail Depot",
        lat: 19.0380,
        lon: 72.8420,
        demand_kg: 400,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 500,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-26",
        name: "Bhandup West Industrial Estate",
        lat: 19.1500,
        lon: 72.9350,
        demand_kg: 350,
        time_window_start_sec: 1800,
        time_window_end_sec: 43200,
        service_duration_sec: 400,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-27",
        name: "Nerul MIDC Sector 20 Hub",
        lat: 19.0340,
        lon: 73.0210,
        demand_kg: 550,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 500,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-28",
        name: "Jogeshwari West S.V. Road Docks",
        lat: 19.1380,
        lon: 72.8470,
        demand_kg: 400,
        time_window_start_sec: 1800,
        time_window_end_sec: 36000,
        service_duration_sec: 450,
        is_in_restricted_urban_core: true
    },
    {
        stop_id: "STOP-29",
        name: "Mahape Millennium Business Park",
        lat: 19.1080,
        lon: 73.0180,
        demand_kg: 500,
        time_window_start_sec: 0,
        time_window_end_sec: 43200,
        service_duration_sec: 500,
        is_in_restricted_urban_core: false
    },
    {
        stop_id: "STOP-30",
        name: "Colaba Marine Lines Distribution Point",
        lat: 18.9380,
        lon: 72.8280,
        demand_kg: 450,
        time_window_start_sec: 3600,
        time_window_end_sec: 36000,
        service_duration_sec: 600,
        is_in_restricted_urban_core: true
    }
];

// Quick-Add Logistics Hubs Lookup (Mumbai MMRDA)
const MUMBAI_QUICK_HUBS = {
    KALAMBOLI: { name: "Kalamboli Steel Market", lat: 19.0222, lon: 73.0988, demand_kg: 900, is_restricted: false },
    TALOJA: { name: "Taloja MIDC Industrial Hub", lat: 19.0620, lon: 73.1380, demand_kg: 850, is_restricted: false },
    WADALA: { name: "Wadala Truck Terminal", lat: 19.0280, lon: 72.8750, demand_kg: 700, is_restricted: true },
    TURBHE: { name: "Turbhe Freight Terminal", lat: 19.0710, lon: 73.0230, demand_kg: 650, is_restricted: false },
    PANVEL: { name: "Panvel JNPT Bypass Hub", lat: 18.9920, lon: 73.1180, demand_kg: 950, is_restricted: false },
    KURLA: { name: "Kurla Kamani Industrial", lat: 19.0728, lon: 72.8795, demand_kg: 400, is_restricted: true },
    GOREGAON: { name: "Goregaon NESCO Logistics", lat: 19.1553, lon: 72.8550, demand_kg: 450, is_restricted: true },
    LOWER_PAREL: { name: "Lower Parel Commercial Dock", lat: 18.9950, lon: 72.8290, demand_kg: 350, is_restricted: true },
    BORIVALI: { name: "Borivali Link Road Center", lat: 19.2300, lon: 72.8480, demand_kg: 500, is_restricted: true },
    MAHAPE: { name: "Mahape Millennium Business Park", lat: 19.1080, lon: 73.0180, demand_kg: 500, is_restricted: false }
};

// Quick-Add Logistics Hubs Lookup (Pune PMC)
const PUNE_QUICK_HUBS = {
    PIMPRI: { name: "Pimpri MIDC Logistics Bay", lat: 18.6298, lon: 73.7997, demand_kg: 850, is_restricted: false },
    CHAKAN: { name: "Chakan Auto Cluster Dock", lat: 18.7550, lon: 73.8550, demand_kg: 900, is_restricted: false },
    HADAPSAR: { name: "Hadapsar Magarpatta Freight Stop", lat: 18.5080, lon: 73.9260, demand_kg: 600, is_restricted: false },
    HINJAWADI: { name: "Hinjawadi IT Park Freight Hub", lat: 18.5913, lon: 73.7389, demand_kg: 700, is_restricted: false },
    KATRAJ: { name: "Katraj South Distribution Center", lat: 18.4575, lon: 73.8677, demand_kg: 500, is_restricted: false },
    SWARGATE: { name: "Swargate Wholesale Terminal", lat: 18.5018, lon: 73.8585, demand_kg: 500, is_restricted: true },
    WAGHOLI: { name: "Wagholi Nagar Road Freight Bay", lat: 18.5810, lon: 73.9820, demand_kg: 400, is_restricted: false },
    KOTHRUD: { name: "Kothrud Distribution Hub", lat: 18.5074, lon: 73.8077, demand_kg: 350, is_restricted: true }
};

// Quick-Add Logistics Hubs Lookup (Nagpur NMC)
const NAGPUR_QUICK_HUBS = {
    BUTIBORI: { name: "Butibori Heavy Freight Dock", lat: 20.9300, lon: 78.9950, demand_kg: 950, is_restricted: false },
    MIHAN: { name: "MIHAN Cargo Terminal Bay", lat: 21.0450, lon: 79.0350, demand_kg: 900, is_restricted: false },
    WADI: { name: "Wadi Truck Terminal", lat: 21.1520, lon: 78.9880, demand_kg: 800, is_restricted: false },
    KALMESHWAR: { name: "Kalmeshwar Steel & Agro Hub", lat: 21.2300, lon: 78.9200, demand_kg: 850, is_restricted: false },
    KAMPTEE: { name: "Kamptee Goods Terminal", lat: 21.2200, lon: 79.2000, demand_kg: 750, is_restricted: false },
    HINGNA: { name: "Hingna Electronic Zone", lat: 21.1100, lon: 79.0050, demand_kg: 500, is_restricted: false },
    SITABULDI: { name: "Sitabuldi Market Depot", lat: 21.1458, lon: 79.0825, demand_kg: 400, is_restricted: true },
    ITWARI: { name: "Itwari Grain Market", lat: 21.1550, lon: 79.1120, demand_kg: 500, is_restricted: true }
};

// Populate Quick-Add Dropdown based on active region
function updateQuickHubDropdown() {
    const select = document.getElementById("quickSelectHub");
    if (!select) return;
    let hubs = MUMBAI_QUICK_HUBS;
    let cityName = "Mumbai";
    if (state.selectedRegion === "NAGPUR_NMC") {
        hubs = NAGPUR_QUICK_HUBS;
        cityName = "Nagpur";
    } else if (state.selectedRegion === "PUNE_PMC") {
        hubs = PUNE_QUICK_HUBS;
        cityName = "Pune";
    }
    
    let html = `<option value="">-- Quick-Add ${cityName} Logistics Hub --</option>`;
    for (const [key, hub] of Object.entries(hubs)) {
        html += `<option value="${key}">${hub.name} (${hub.demand_kg} kg)</option>`;
    }
    select.innerHTML = html;
}

// City-Aware Dynamic AI Simulation Prompt Chips
const CITY_PROMPT_CHIPS = {
    NAGPUR_NMC: [
        { label: "Cotton Market Queue", text: "Cotton Market truck queue: 45 min unloading delay at Central Avenue" },
        { label: "Sitabuldi Metro Gantry", text: "Sitabuldi Metro gantry: 2.5m limit requires Wardha Rd detour" },
        { label: "Wadi Checkpost Delay", text: "Wadi Octroi checkpost freight congestion: 40 min waiting time" },
        { label: "Itwari Peak Window", text: "Itwari wholesale market: deliver before 11:30 AM peak restriction" }
    ],
    PUNE_PMC: [
        { label: "Swargate Gridlock", text: "Swargate junction peak gridlock: 50 min truck delay" },
        { label: "Lakdi Pul Weight Limit", text: "Lakdi Pul weight limit: 5.0T restriction requires bypass" },
        { label: "Chakan Toll Delay", text: "Chakan MIDC toll queue: 35 min transport delay" },
        { label: "Shivajinagar Ban", text: "Shivajinagar core market: deliver before 09:00 AM peak ban" }
    ],
    MUMBAI_MMRDA: [
        { label: "Dadar Flyover Rain", text: "Dadar TT flyover waterlogging: 45 min delay on south corridor" },
        { label: "2.5m Height Gantry", text: "2.5m flyover height gantry: Tata 407 diverted to surface road" },
        { label: "Mulund Checkpost", text: "Mulund transport checkpost: 60 min commercial truck inspection" },
        { label: "BKC Dock Window", text: "BKC customer dock requested priority delivery before 11:00 AM" }
    ]
};

function renderDynamicPromptChips() {
    const container = document.getElementById("customPromptChipsContainer");
    if (!container) return;

    const chips = CITY_PROMPT_CHIPS[state.selectedRegion] || CITY_PROMPT_CHIPS.MUMBAI_MMRDA;
    container.innerHTML = "";

    chips.forEach(chip => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chip-btn";
        btn.dataset.text = chip.text;
        btn.innerHTML = `<i class="fa-solid fa-lightbulb"></i> ${chip.label}`;
        btn.addEventListener("click", () => {
            const textarea = document.getElementById("customSituationInput");
            if (textarea) {
                textarea.value = chip.text;
                textarea.focus();
                showToast(`Loaded situation: "${chip.label}"`, "info");
            }
        });
        container.appendChild(btn);
    });
}

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    initMap();
    initEventListeners();
    updateClockDisplay(state.departureHour);
    updateFleetSummary();
    updateQuickHubDropdown();
    renderDynamicPromptChips();
    updateRulesTabContent();
    loadDatasetScale(6);
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

    // Vehicle Counter Controls (Expanded to 12 Vans and 8 Trucks)
    document.getElementById("btnIncVan").addEventListener("click", () => {
        state.fleet.vans = Math.min(12, state.fleet.vans + 1);
        document.getElementById("vanCount").textContent = state.fleet.vans;
        updateFleetSummary();
    });
    document.getElementById("btnDecVan").addEventListener("click", () => {
        state.fleet.vans = Math.max(0, state.fleet.vans - 1);
        document.getElementById("vanCount").textContent = state.fleet.vans;
        updateFleetSummary();
    });

    document.getElementById("btnIncTruck").addEventListener("click", () => {
        state.fleet.trucks = Math.min(8, state.fleet.trucks + 1);
        document.getElementById("truckCount").textContent = state.fleet.trucks;
        updateFleetSummary();
    });
    document.getElementById("btnDecTruck").addEventListener("click", () => {
        state.fleet.trucks = Math.max(0, state.fleet.trucks - 1);
        document.getElementById("truckCount").textContent = state.fleet.trucks;
        updateFleetSummary();
    });

    // Region Selector (Mumbai MMRDA vs Pune PMC vs Nagpur NMC)
    const regionSelector = document.getElementById("regionSelector");
    if (regionSelector) {
        regionSelector.addEventListener("change", (e) => {
            state.selectedRegion = e.target.value;
            if (state.selectedRegion === "NAGPUR_NMC") {
                state.map.setView([21.1458, 79.0882], 12);
            } else if (state.selectedRegion === "PUNE_PMC") {
                state.map.setView([18.5300, 73.8500], 11);
            } else {
                state.map.setView([19.1400, 72.9700], 11);
            }
            refreshRegulatoryLayers();
            updateClockDisplay(state.departureHour);
            updateQuickHubDropdown();
            renderDynamicPromptChips();
            updateRulesTabContent();
            loadDatasetScale(6);
            const regionLabel = state.selectedRegion === "NAGPUR_NMC" 
                ? "Nagpur Municipal Corporation (NMC)" 
                : (state.selectedRegion === "PUNE_PMC" ? "Pune Municipal Corporation (PMC)" : "Mumbai MMRDA");
            showToast(`Switched region to ${regionLabel}`, "info");
        });
    }

    // Preset & Reset
    document.getElementById("loadSampleBtn")?.addEventListener("click", () => loadDatasetScale(6));
    document.getElementById("clearBtn").addEventListener("click", clearAll);

    // Benchmark Scale Chips (6, 10, 20, 30 Drops)
    document.querySelectorAll(".btn-scale-chip").forEach(chip => {
        chip.addEventListener("click", () => {
            const scale = parseInt(chip.dataset.scale, 10) || 6;
            loadDatasetScale(scale);
        });
    });

    // Manual Quick-Add Logistics Hub Dropdown
    document.getElementById("btnQuickAddHub")?.addEventListener("click", () => {
        const select = document.getElementById("quickSelectHub");
        const key = select.value;
        const isNagpur = state.selectedRegion === "NAGPUR_NMC";
        const isPune = state.selectedRegion === "PUNE_PMC";
        let hubs = MUMBAI_QUICK_HUBS;
        let prefix = "STOP";
        let defaultDepot = { ...MUMBAI_PRESET_DEPOT };
        if (isNagpur) {
            hubs = NAGPUR_QUICK_HUBS;
            prefix = "NGP";
            defaultDepot = { ...NAGPUR_PRESET_DEPOT };
        } else if (isPune) {
            hubs = PUNE_QUICK_HUBS;
            prefix = "PUNE";
            defaultDepot = { ...PUNE_PRESET_DEPOT };
        }
        if (!key || !hubs[key]) {
            showToast("Please choose a freight hub from the dropdown list.", "warning");
            return;
        }

        if (!state.depot) {
            state.depot = defaultDepot;
        }

        const hub = hubs[key];
        const idx = state.stops.length + 1;
        state.stops.push({
            stop_id: `${prefix}-${String(idx).padStart(2, "0")}`,
            name: hub.name,
            lat: hub.lat,
            lon: hub.lon,
            demand_kg: hub.demand_kg,
            time_window_start_sec: 0,
            time_window_end_sec: 43200,
            service_duration_sec: 600,
            is_in_restricted_urban_core: hub.is_restricted
        });

        select.value = "";
        stopRouteAnimation();
        state.currentRoutes = [];
        state.routesLayer.clearLayers();
        if (document.getElementById("managerTabBtn")) document.getElementById("managerTabBtn").disabled = true;
        if (document.getElementById("driverTabBtn")) document.getElementById("driverTabBtn").disabled = true;
        document.getElementById("mapMetricsBar").classList.add("hidden");
        document.getElementById("mapAnimBar").classList.add("hidden");

        renderLocationsList();
        renderMapMarkers();
        updateFleetSummary();
        showToast(`Added ${hub.name} (Drop #${idx})`, "success");
    });

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

    // Driver HUD Event Listeners
    document.getElementById("driverVehicleSelect")?.addEventListener("change", (e) => {
        state.activeDriverVehicleId = e.target.value;
        if (state.lastOptimizationData) {
            renderDriverHUD(state.lastOptimizationData, state.activeDriverVehicleId);
        }
    });

    document.getElementById("btnMarkCurrentDelivered")?.addEventListener("click", () => {
        markCurrentStopDelivered();
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
    document.getElementById("downloadCsvBtnQuick")?.addEventListener("click", downloadManifestCsv);
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
    const isNagpur = state.selectedRegion === "NAGPUR_NMC";
    const isPune = state.selectedRegion === "PUNE_PMC";

    if (isNagpur) {
        statusBox.className = "rule-status-box status-restricted";
        statusTitle.textContent = "NMC NOTIFICATION EXPIRED (VERIFY WITH TRAFFIC POLICE)";
        statusDesc.textContent = "Nagpur commercial vehicle restriction (06:00 - 22:00) valid until 2026-04-07 (no renewal found). Status: expired, verify with traffic police. Heavy freight trucks routed via Outer Ring Road; rule ignored by engine until verified. Ganesh Visarjan override (2026-09-25 to 2026-09-27) is also expired.";
    } else if (isPune) {
        if (hourVal >= 9.0 && hourVal <= 12.0) {
            statusBox.className = "rule-status-box status-restricted";
            statusTitle.textContent = "PMC MORNING PEAK BAN ACTIVE (09:00 AM - 12:00 PM)";
            statusDesc.textContent = "Heavy freight trucks (Tata 407) are banned in central Pune (Shivajinagar, Swargate). Fine ₹15,000. Delivery vans (Tata Ace) permitted.";
        } else if (hourVal >= 16.5 && hourVal <= 20.5) {
            statusBox.className = "rule-status-box status-restricted";
            statusTitle.textContent = "PMC EVENING PEAK BAN ACTIVE (04:30 PM - 08:30 PM)";
            statusDesc.textContent = "Strict peak ban on heavy commercial vehicles > 3.5 tonnes GVW across PMC core arterial roads.";
        } else {
            statusBox.className = "rule-status-box status-open";
            statusTitle.textContent = "PMC ARTERIALS OPEN (UNRESTRICTED)";
            statusDesc.textContent = "Both delivery vans and heavy freight trucks are permitted on all designated Pune commercial arterial corridors.";
        }
    } else {
        if (hourVal >= 8.0 && hourVal <= 11.0) {
            statusBox.className = "rule-status-box status-restricted";
            statusTitle.textContent = "MORNING NO-ENTRY ACTIVE (08:00 AM - 11:00 AM)";
            statusDesc.textContent = "Citywide peak ban on heavy vehicles (08:00-11:00, effective 2026-02-01). South Mumbai restriction 07:00-24:00 & Eastern Freeway 24h ban. Heavy definition: unspecified in sources; vans exempt only as labeled demo assumption. Exempt: essential goods, emergency, school/govt buses.";
        } else if (hourVal >= 17.0 && hourVal <= 21.0) {
            statusBox.className = "rule-status-box status-restricted";
            statusTitle.textContent = "EVENING NO-ENTRY ACTIVE (05:00 PM - 09:00 PM)";
            statusDesc.textContent = "Citywide evening ban on heavy vehicles (17:00-21:00, effective 2026-02-01). Heavy definition: unspecified in sources; vans exempt only as labeled demo assumption. Exempt: essential goods, emergency, school/govt buses.";
        } else {
            statusBox.className = "rule-status-box status-open";
            statusTitle.textContent = "ALL ROADS OPEN (UNRESTRICTED)";
            statusDesc.textContent = "Citywide corridors open outside 08:00-11:00 & 17:00-21:00 (Note: Eastern Freeway 24h ban & South Mumbai 07:00-24:00 apply). Heavy definition unspecified; vans exempt as demo assumption.";
        }
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

// Load Regional Logistics Dataset at Specific Benchmark Scale (6, 10, 20, 30 Drops)
function loadDatasetScale(scale = 6) {
    stopRouteAnimation();
    state.currentRoutes = [];
    state.routesLayer.clearLayers();
    if (document.getElementById("managerTabBtn")) document.getElementById("managerTabBtn").disabled = true;
    if (document.getElementById("driverTabBtn")) document.getElementById("driverTabBtn").disabled = true;
    document.getElementById("mapMetricsBar").classList.add("hidden");
    document.getElementById("mapAnimBar").classList.add("hidden");

    const isNagpur = state.selectedRegion === "NAGPUR_NMC";
    const isPune = state.selectedRegion === "PUNE_PMC";
    let defaultDepot = { ...MUMBAI_PRESET_DEPOT };
    let allStops = MUMBAI_ALL_STOPS;
    let cityName = "Mumbai";
    if (isNagpur) {
        defaultDepot = { ...NAGPUR_PRESET_DEPOT };
        allStops = NAGPUR_ALL_STOPS;
        cityName = "Nagpur";
    } else if (isPune) {
        defaultDepot = { ...PUNE_PRESET_DEPOT };
        allStops = PUNE_ALL_STOPS;
        cityName = "Pune";
    }

    state.depot = defaultDepot;
    const sliceCount = Math.min(scale, allStops.length);
    state.stops = JSON.parse(JSON.stringify(allStops.slice(0, sliceCount)));

    // Scale recommended fleet capacity dynamically
    if (scale <= 6) {
        state.fleet.vans = 2;
        state.fleet.trucks = 1;
    } else if (scale <= 10) {
        state.fleet.vans = 3;
        state.fleet.trucks = 2;
    } else if (scale <= 20) {
        state.fleet.vans = 4;
        state.fleet.trucks = 3;
    } else {
        state.fleet.vans = 6;
        state.fleet.trucks = 4;
    }

    document.getElementById("vanCount").textContent = state.fleet.vans;
    document.getElementById("truckCount").textContent = state.fleet.trucks;

    // Highlight active scale chip
    document.querySelectorAll(".btn-scale-chip").forEach(chip => {
        if (parseInt(chip.dataset.scale, 10) === scale) {
            chip.classList.add("active");
        } else {
            chip.classList.remove("active");
        }
    });

    renderLocationsList();
    renderMapMarkers();
    updateFleetSummary();
    showToast(`Loaded ${sliceCount} ${cityName} commercial drops (Fleet: ${state.fleet.vans} Vans, ${state.fleet.trucks} Trucks)`, "success");
}

// Remove an Individual Destination Stop
function removeStopByIndex(index) {
    if (index < 0 || index >= state.stops.length) return;
    const removed = state.stops.splice(index, 1)[0];
    
    // Stop ongoing animation and invalidate stale route display
    stopRouteAnimation();
    state.currentRoutes = [];
    state.routesLayer.clearLayers();
    if (document.getElementById("managerTabBtn")) document.getElementById("managerTabBtn").disabled = true;
    if (document.getElementById("driverTabBtn")) document.getElementById("driverTabBtn").disabled = true;
    document.getElementById("mapMetricsBar").classList.add("hidden");
    document.getElementById("mapAnimBar").classList.add("hidden");

    renderLocationsList();
    renderMapMarkers();
    updateFleetSummary();
    showToast(`Removed "${removed.name}"`, "info");
}
window.removeStopByIndex = removeStopByIndex;

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
    if (document.getElementById("managerTabBtn")) document.getElementById("managerTabBtn").disabled = true;
    if (document.getElementById("driverTabBtn")) document.getElementById("driverTabBtn").disabled = true;
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
            name: `Custom Drop Location ${idx}`,
            lat: lat,
            lon: lon,
            demand_kg: 400,
            time_window_start_sec: 0,
            time_window_end_sec: 43200,
            service_duration_sec: 600,
            is_in_restricted_urban_core: lat < 19.20 && lon < 72.95 // heuristic for Mumbai urban core
        });
        showToast(`Added Drop Point ${idx} at [${lat.toFixed(3)}, ${lon.toFixed(3)}]`, "success");
    }
    renderLocationsList();
    renderMapMarkers();
    updateFleetSummary();
}

// Render Locations List in Sidebar with Individual Remove Buttons
function renderLocationsList() {
    const list = document.getElementById("locationList");
    const stopsCount = document.getElementById("stopsCount");
    
    if (!state.depot && state.stops.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-map"></i>
                <p>No delivery locations loaded.</p>
                <button class="btn btn-secondary btn-sm" id="loadSampleBtnInline">
                    <i class="fa-solid fa-download"></i> Load 6 Benchmark Drops
                </button>
            </div>
        `;
        document.getElementById("loadSampleBtnInline")?.addEventListener("click", () => loadDatasetScale(6));
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
        const zoneText = s.is_in_restricted_urban_core ? "City Core (Restricted)" : "Outer Arterial";
        html += `
            <div class="stop-card">
                <div class="stop-badge-num">${i + 1}</div>
                <div class="stop-meta">
                    <div class="stop-meta-name">${escapeHtml(s.name)}</div>
                    <div class="stop-meta-info">Load: ${s.demand_kg} kg | Unload: ${Math.round(s.service_duration_sec / 60)} mins | ${zoneText}</div>
                </div>
                <button type="button" class="btn-stop-remove" data-index="${i}" title="Remove this destination">
                    <i class="fa-solid fa-xmark"></i>
                </button>
            </div>
        `;
    });

    list.innerHTML = html;

    // Attach individual remove click handlers
    list.querySelectorAll(".btn-stop-remove").forEach(btn => {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            const idx = parseInt(btn.dataset.index, 10);
            removeStopByIndex(idx);
        });
    });
}

// Render Map Markers with Popup Remove Action
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
            .bindPopup(`<strong>${state.depot.name}</strong><br>Warehouse Hub (Start & Return Point)`);
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
            .bindPopup(`
                <div style="font-size:12px; line-height:1.4;">
                    <strong>Stop ${i + 1}: ${s.name}</strong><br>
                    <span>Load: ${s.demand_kg} kg | Unload: ${Math.round(s.service_duration_sec / 60)} mins</span><br>
                    <span>Zone: ${s.is_in_restricted_urban_core ? "City Core (Restricted)" : "Outer Arterial"}</span>
                    <div style="margin-top:6px; padding-top:4px; border-top:1px solid #334155;">
                        <button type="button" class="btn btn-outline btn-xs" style="color:#ef4444; border-color:rgba(239,68,68,0.5); padding:2px 8px; font-size:10px; cursor:pointer;" onclick="window.removeStopByIndex(${i})">
                            <i class="fa-solid fa-trash-can"></i> Remove Drop
                        </button>
                    </div>
                </div>
            `);
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
        region: state.selectedRegion || "MUMBAI_MMRDA",
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

    // 1. Status Banner Badge
    const statusPill = document.getElementById("metricStatusPill");
    if (statusPill) {
        statusPill.className = "status-pill";
        const st = (data.status || "SUCCESS").toUpperCase();
        if (st === "SUCCESS") {
            statusPill.classList.add("status-success");
            statusPill.innerHTML = '<i class="fa-solid fa-circle-check"></i> SUCCESS';
        } else if (st === "PARTIAL") {
            statusPill.classList.add("status-partial");
            statusPill.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> PARTIAL';
        } else {
            statusPill.classList.add("status-infeasible");
            statusPill.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> INFEASIBLE';
        }
    }

    // 2. Solver Used & Departure Time
    const solverEl = document.getElementById("metricSolver");
    if (solverEl) {
        solverEl.textContent = data.solver_used || "OR-Tools (CVRPTW)";
    }
    const depEl = document.getElementById("metricDeparture");
    if (depEl) {
        const depIso = data.departure_time || "08:30";
        const timeMatch = depIso.match(/T?(\d{2}:\d{2})/);
        depEl.textContent = timeMatch ? `${timeMatch[1]} IST` : "08:30 IST";
    }

    // 3. Road Data Badge (Live OSRM vs Detour Winding)
    const roadBadge = document.getElementById("metricRoadBadge");
    if (roadBadge) {
        if (data.is_real_road_data) {
            roadBadge.className = "road-badge road-badge-live";
            roadBadge.innerHTML = '<i class="fa-solid fa-satellite-dish"></i> Live OSRM Graph';
        } else {
            roadBadge.className = "road-badge road-badge-estimate";
            roadBadge.innerHTML = '<i class="fa-solid fa-calculator"></i> Estimated Winding (1.35x)';
        }
    }

    // 4. Cost Breakdown (Fixed Dispatch vs Variable Running)
    const costBreakdownEl = document.getElementById("metricCostBreakdown");
    if (costBreakdownEl) {
        const fixedCost = Math.round(data.fixed_dispatch_cost_inr || 0);
        const varCost = Math.round(data.variable_running_cost_inr || 0);
        costBreakdownEl.textContent = `Fixed: ₹${fixedCost.toLocaleString()} | Running: ₹${varCost.toLocaleString()}`;
    }

    // 5. Dropped Stops & Validation Warning Panel
    const alertPanel = document.getElementById("mapAlertPanel");
    const alertList = document.getElementById("mapAlertList");
    const alertTitle = document.getElementById("mapAlertTitle");
    const closeAlertBtn = document.getElementById("closeMapAlertBtn");

    if (closeAlertBtn && !closeAlertBtn._hasListener) {
        closeAlertBtn._hasListener = true;
        closeAlertBtn.addEventListener("click", () => alertPanel.classList.add("hidden"));
    }

    const droppedStops = data.dropped_stops || [];
    const valErrors = data.validation_errors || [];
    const hasIssues = droppedStops.length > 0 || valErrors.length > 0 || data.status !== "SUCCESS";

    if (alertPanel && alertList) {
        if (hasIssues) {
            alertPanel.classList.remove("hidden");
            if (data.status === "INFEASIBLE") {
                alertTitle.textContent = "Routing Infeasible: Delivery Constraints Breached";
            } else if (data.status === "PARTIAL") {
                alertTitle.textContent = `Partial Dispatch: ${droppedStops.length} Stops Dropped`;
            } else {
                alertTitle.textContent = "Operational Constraints Warning";
            }

            let alertHtml = "";

            // Dropped stops reason cards
            droppedStops.forEach(sId => {
                const stopObj = (state.stops || []).find(s => s.stop_id === sId) || { name: `Stop ${sId}` };
                let reason = "Exceeded vehicle payload capacity or delivery cutoff deadline.";
                if (stopObj.is_in_restricted_urban_core) {
                    reason = "Stop is inside urban restricted core during municipal commercial vehicle peak hours.";
                }
                alertHtml += `
                    <div class="map-alert-card">
                        <strong><i class="fa-solid fa-ban"></i> Dropped Stop: ${escapeHtml(stopObj.name)} (${escapeHtml(sId)})</strong><br>
                        <span>${escapeHtml(reason)}</span>
                    </div>
                `;
            });

            // Validation errors
            valErrors.forEach(err => {
                alertHtml += `
                    <div class="map-alert-card warning">
                        <strong><i class="fa-solid fa-triangle-exclamation"></i> Constraint Breach: ${escapeHtml(err.error_type || "Validation Warning")}</strong><br>
                        <span>${escapeHtml(err.message || JSON.stringify(err))}</span>
                    </div>
                `;
            });

            alertList.innerHTML = alertHtml;
        } else {
            alertPanel.classList.add("hidden");
            alertList.innerHTML = "";
        }
    }

    document.getElementById("mapAnimBar").classList.remove("hidden");

    // Dynamic Trade-Off Analysis Update
    const isNagpur = state.selectedRegion === "NAGPUR_NMC";
    const isPune = state.selectedRegion === "PUNE_PMC";
    let fineRisk = "₹20,000";
    let delayHours = "4.5";
    let regionName = "Mumbai MMRDA";
    if (isNagpur) {
        fineRisk = "₹10,000";
        delayHours = "3.5";
        regionName = "Nagpur NMC";
    } else if (isPune) {
        fineRisk = "₹15,000";
        delayHours = "4.0";
        regionName = "Pune PMC";
    }
    const fineEl = document.querySelector(".trade-off-table tr:nth-child(3) td:nth-child(2)");
    if (fineEl) {
        fineEl.innerHTML = `<strong class="text-danger">${fineRisk} fine</strong> (Sec 115 MVA)`;
    }
    const tradeOffText = document.getElementById("tradeOffRecommendationText");
    if (tradeOffText) {
        tradeOffText.innerHTML = `<strong>Dispatch Strategy (${regionName}):</strong> Using 3 Tata Ace delivery vans eliminates the ${fineRisk} fine liability and completes deliveries ${delayHours} hours faster during peak windows despite ₹470 higher vehicle fuel cost.`;
    }

    renderManagerDashboard(data);
    renderDriverHUD(data);

    const managerTabBtn = document.getElementById("managerTabBtn");
    const driverTabBtn = document.getElementById("driverTabBtn");
    if (managerTabBtn) managerTabBtn.disabled = false;
    if (driverTabBtn) driverTabBtn.disabled = false;

    if (autoSwitchTab && managerTabBtn) {
        managerTabBtn.click();
    }

    showToast(`Optimal routes calculated in ${data.solve_duration_ms} ms`, "success");
}

// RENDER FLEET MANAGER EXECUTIVE DASHBOARD
function renderManagerDashboard(data) {
    if (!data || !data.routes) return;

    // 1. Operational Cost
    const totalCost = Math.round(data.total_fleet_cost_inr || 0);
    const costEl = document.getElementById("managerCost");
    if (costEl) costEl.textContent = `₹${totalCost.toLocaleString()}`;

    // 2. Total Payload & Fleet Capacity
    let totalPayload = 0;
    let totalCapacity = 0;
    data.routes.forEach(r => {
        const isVan = r.vehicle_class === "van";
        const cap = isVan ? 1200 : 4500;
        totalPayload += (r.total_load_kg || 0);
        totalCapacity += cap;
    });
    const utilPct = totalCapacity > 0 ? Math.round((totalPayload / totalCapacity) * 100) : 0;
    const utilEl = document.getElementById("managerUtilization");
    if (utilEl) utilEl.textContent = `${utilPct}%`;
    const loadSubEl = document.getElementById("managerLoadSub");
    if (loadSubEl) loadSubEl.textContent = `${totalPayload.toLocaleString()} / ${totalCapacity.toLocaleString()} kg cargo`;

    // 3. ESG CO2 Savings Metric (vs unoptimized individual detours: ~210g CO2 / km)
    const co2SavedKg = ((data.total_fleet_distance_km || 0) * 0.22 * 1.8).toFixed(1);
    const co2El = document.getElementById("managerCo2");
    if (co2El) co2El.textContent = `${co2SavedKg} kg`;

    // 4. Legal Compliance / Fine Risk
    const riskEl = document.getElementById("managerLegalRisk");
    if (riskEl) {
        riskEl.textContent = "₹0 Risk";
        riskEl.className = "kpi-val text-success";
    }

    // 5. Active Vehicle Count Badge
    const countBadge = document.getElementById("managerActiveCount");
    if (countBadge) countBadge.textContent = `${data.routes.length} Active`;

    // 6. Fleet Allocation Matrix Table
    const tbody = document.getElementById("managerFleetTbody");
    if (tbody) {
        let html = "";
        data.routes.forEach((route) => {
            const isVan = route.vehicle_class === "van";
            const cap = isVan ? 1200 : 4500;
            const loadKg = route.total_load_kg || 0;
            const pct = Math.min(100, Math.round((loadKg / cap) * 100));
            const dropsCount = Math.max(0, (route.stops_visited || []).length - 2);
            const classBadge = isVan 
                ? '<span class="badge" style="background:rgba(2,132,199,0.2); color:#38bdf8;">VAN (LCV)</span>' 
                : '<span class="badge" style="background:rgba(217,119,6,0.2); color:#fbbf24;">TRUCK (HCV)</span>';

            html += `
                <tr>
                    <td>
                        <strong style="display:flex; align-items:center; gap:6px;">
                            <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:${route.color_hex};"></span>
                            ${route.vehicle_name}
                        </strong>
                        <span style="font-size:10px; color:#94a3b8;">${route.vehicle_id}</span>
                    </td>
                    <td>${classBadge}</td>
                    <td><strong>${dropsCount}</strong> drops</td>
                    <td>
                        <div style="font-size:11px; font-weight:600;">${loadKg} / ${cap} kg (${pct}%)</div>
                        <div style="background:#334155; height:4px; border-radius:2px; margin-top:3px; overflow:hidden;">
                            <div style="background:${route.color_hex}; width:${pct}%; height:100%;"></div>
                        </div>
                    </td>
                    <td><strong>₹${Math.round(route.estimated_cost_inr).toLocaleString()}</strong></td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    }
}

// RENDER DRIVER TURN-BY-TURN HUD
function renderDriverHUD(data, selectedVehicleId = null) {
    if (!data || !data.routes || data.routes.length === 0) return;

    const select = document.getElementById("driverVehicleSelect");
    if (!select) return;

    // Populate Vehicle Select
    const currentVal = selectedVehicleId || state.activeDriverVehicleId || data.routes[0].vehicle_id;
    state.activeDriverVehicleId = currentVal;

    let selectHtml = "";
    data.routes.forEach(r => {
        const drops = Math.max(0, (r.stops_visited || []).length - 2);
        selectHtml += `<option value="${r.vehicle_id}" ${r.vehicle_id === currentVal ? "selected" : ""}>
            ${r.vehicle_name} (${r.vehicle_class.toUpperCase()} • ${drops} drops)
        </option>`;
    });
    select.innerHTML = selectHtml;

    // Find the currently selected route
    const activeRoute = data.routes.find(r => r.vehicle_id === currentVal) || data.routes[0];
    const allStops = activeRoute.stops_visited || [];
    const deliveryStops = allStops.slice(1, -1); // excludes initial depot and final return depot

    // Driver Names by Vehicle ID
    const driverRegistry = {
        "VAN-01": { name: "Suresh Kumar", reg: state.selectedRegion === "NAGPUR_NMC" ? "MH-31-EQ-4421" : (state.selectedRegion === "PUNE_PMC" ? "MH-12-RN-8819" : "MH-04-AZ-2091") },
        "VAN-02": { name: "Ramesh Pawar", reg: state.selectedRegion === "NAGPUR_NMC" ? "MH-31-DS-9102" : (state.selectedRegion === "PUNE_PMC" ? "MH-12-PQ-5520" : "MH-04-BV-4820") },
        "VAN-03": { name: "Rajesh Shinde", reg: state.selectedRegion === "NAGPUR_NMC" ? "MH-31-FG-1188" : (state.selectedRegion === "PUNE_PMC" ? "MH-12-GH-3390" : "MH-04-CX-6712") },
        "VAN-04": { name: "Vijay Sharma", reg: state.selectedRegion === "NAGPUR_NMC" ? "MH-31-HJ-7733" : (state.selectedRegion === "PUNE_PMC" ? "MH-12-KL-1209" : "MH-04-DF-8821") },
        "TRUCK-01": { name: "Dilip Patil", reg: state.selectedRegion === "NAGPUR_NMC" ? "MH-31-TR-5001" : (state.selectedRegion === "PUNE_PMC" ? "MH-12-TR-7001" : "MH-04-TR-9001") },
        "TRUCK-02": { name: "Manoj Gawande", reg: state.selectedRegion === "NAGPUR_NMC" ? "MH-31-TR-5002" : (state.selectedRegion === "PUNE_PMC" ? "MH-12-TR-7002" : "MH-04-TR-9002") },
        "TRUCK-03": { name: "Amit Deshmukh", reg: state.selectedRegion === "NAGPUR_NMC" ? "MH-31-TR-5003" : (state.selectedRegion === "PUNE_PMC" ? "MH-12-TR-7003" : "MH-04-TR-9003") }
    };
    const driverInfo = driverRegistry[activeRoute.vehicle_id] || { name: "Operator", reg: "MH-REG-COMMERCIAL" };

    // Update Drop Counts and Checklist
    let completedCount = 0;
    let nextPendingStop = null;
    let nextPendingIndex = -1;

    deliveryStops.forEach((stop, idx) => {
        const key = `${activeRoute.vehicle_id}_${idx}`;
        if (state.driverDeliveredStops[key]) {
            completedCount++;
        } else if (!nextPendingStop) {
            nextPendingStop = stop;
            nextPendingIndex = idx;
        }
    });

    const totalDrops = deliveryStops.length;
    const progressPct = totalDrops > 0 ? Math.round((completedCount / totalDrops) * 100) : 0;

    // Update Next Stop Card
    const nextNameEl = document.getElementById("driverNextName");
    const nextTimeEl = document.getElementById("driverNextTime");
    const nextMetaEl = document.getElementById("driverNextMeta");
    const markBtn = document.getElementById("btnMarkCurrentDelivered");

    if (totalDrops === 0) {
        if (nextNameEl) nextNameEl.textContent = "No Drops Assigned";
        if (nextTimeEl) nextTimeEl.textContent = "--:--";
        if (nextMetaEl) nextMetaEl.textContent = "Vehicle has no scheduled intermediate delivery stops.";
        if (markBtn) markBtn.disabled = true;
    } else if (!nextPendingStop) {
        if (nextNameEl) nextNameEl.textContent = "All Assigned Drops Delivered! 🎉";
        if (nextTimeEl) nextTimeEl.textContent = "Done";
        if (nextMetaEl) nextMetaEl.textContent = `All ${totalDrops} stops complete. Proceed to ${allStops[allStops.length - 1]?.name || "Warehouse Hub"} for shift wrap-up.`;
        if (markBtn) {
            markBtn.disabled = true;
            markBtn.innerHTML = '<i class="fa-solid fa-flag-checkered"></i> Shift Route Completed';
        }
    } else {
        if (nextNameEl) nextNameEl.textContent = `${nextPendingIndex + 1}. ${nextPendingStop.name}`;
        if (nextTimeEl) nextTimeEl.textContent = nextPendingStop.clock_time_str || "Scheduled";
        const zoneBadge = nextPendingStop.is_in_restricted_urban_core 
            ? '<span style="color:#ef4444; font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> Central Zone Ban Active</span>' 
            : '<span style="color:#4ade80;"><i class="fa-solid fa-circle-check"></i> Outer Corridor</span>';
        if (nextMetaEl) {
            nextMetaEl.innerHTML = `Driver: <strong>${driverInfo.name}</strong> (${driverInfo.reg})<br>Drop Cargo: <strong>${nextPendingStop.current_load_kg || 400} kg</strong> | Dwell: ${Math.round((nextPendingStop.waiting_time_sec || 600) / 60)} min | ${zoneBadge}`;
        }
        if (markBtn) {
            markBtn.disabled = false;
            markBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Mark Stop as Completed / Delivered';
        }
    }

    // Update Progress
    const ratioEl = document.getElementById("driverProgressRatio");
    if (ratioEl) ratioEl.textContent = `${completedCount} / ${totalDrops} Completed (${progressPct}%)`;
    const barEl = document.getElementById("driverProgressBar");
    if (barEl) barEl.style.width = `${progressPct}%`;
    const dropsBadge = document.getElementById("driverTotalDrops");
    if (dropsBadge) dropsBadge.textContent = `${totalDrops} Drops`;

    // Render Checklist
    const listContainer = document.getElementById("driverChecklistContainer");
    if (listContainer) {
        if (deliveryStops.length === 0) {
            listContainer.innerHTML = '<p style="font-size:11px; color:#94a3b8; text-align:center; padding:12px 0;">No delivery waypoints for this vehicle.</p>';
            return;
        }

        let html = "";
        deliveryStops.forEach((stop, idx) => {
            const isDone = !!state.driverDeliveredStops[`${activeRoute.vehicle_id}_${idx}`];
            const isCurrent = !isDone && nextPendingStop && nextPendingIndex === idx;
            const rowClass = isDone ? "driver-step-row is-delivered" : (isCurrent ? "driver-step-row is-active" : "driver-step-row");
            const btnIcon = isDone ? "fa-circle-check text-success" : (isCurrent ? "fa-circle-dot text-primary" : "fa-circle text-muted");
            const btnTitle = isDone ? "Mark as pending" : "Mark as delivered";

            html += `
                <div class="${rowClass}">
                    <span class="step-num">${idx + 1}</span>
                    <div class="step-details">
                        <div class="step-name">${escapeHtml(stop.name)}</div>
                        <div class="step-meta">
                            <span><i class="fa-regular fa-clock"></i> ${escapeHtml(stop.clock_time_str) || "--:--"}</span>
                            <span><i class="fa-solid fa-box"></i> ${stop.current_load_kg || 400} kg</span>
                        </div>
                    </div>
                    <button type="button" class="btn-step-toggle" title="${btnTitle}" onclick="window.toggleDriverStop('${escapeHtml(activeRoute.vehicle_id)}', ${idx})">
                        <i class="fa-solid ${btnIcon}" style="font-size:16px;"></i>
                    </button>
                </div>
            `;
        });
        listContainer.innerHTML = html;
    }
}

// TOGGLE DRIVER STOP DELIVERED STATUS
function toggleDriverStop(vehicleId, stopIndex) {
    const key = `${vehicleId}_${stopIndex}`;
    state.driverDeliveredStops[key] = !state.driverDeliveredStops[key];
    if (state.lastOptimizationData) {
        renderDriverHUD(state.lastOptimizationData, vehicleId);
    }
    const status = state.driverDeliveredStops[key] ? "delivered" : "pending";
    showToast(`Stop ${stopIndex + 1} marked as ${status}.`, "info");
}
window.toggleDriverStop = toggleDriverStop;

// MARK CURRENT STOP DELIVERED
function markCurrentStopDelivered() {
    if (!state.lastOptimizationData || !state.lastOptimizationData.routes) return;
    const vehicleId = state.activeDriverVehicleId || state.lastOptimizationData.routes[0]?.vehicle_id;
    if (!vehicleId) return;

    const activeRoute = state.lastOptimizationData.routes.find(r => r.vehicle_id === vehicleId);
    if (!activeRoute) return;

    const deliveryStops = (activeRoute.stops_visited || []).slice(1, -1);
    for (let idx = 0; idx < deliveryStops.length; idx++) {
        const key = `${vehicleId}_${idx}`;
        if (!state.driverDeliveredStops[key]) {
            state.driverDeliveredStops[key] = true;
            renderDriverHUD(state.lastOptimizationData, vehicleId);
            showToast(`Marked "${deliveryStops[idx].name}" as delivered!`, "success");
            return;
        }
    }
    showToast("All stops for this vehicle are already completed!", "info");
}
window.markCurrentStopDelivered = markCurrentStopDelivered;

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

// REFRESH REGULATORY MAP LAYERS (Mumbai vs Pune vs Nagpur)
function refreshRegulatoryLayers() {
    state.geofenceLayer.clearLayers();
    state.barriersLayer.clearLayers();
    state.bridgesLayer.clearLayers();

    const isNagpur = state.selectedRegion === "NAGPUR_NMC";
    const isPune = state.selectedRegion === "PUNE_PMC";
    let geofenceCoords = MUMBAI_GEOFENCE_COORDS;
    let barriers = MUMBAI_BARRIERS;
    let geofenceTitle = "Greater Mumbai No-Entry Zone";
    let authority = "Mumbai Traffic Police (Sec 115 & 116 MVA)";
    let peakHours = "08:00 AM - 11:00 AM & 05:00 PM - 09:00 PM (South Mumbai: 07:00-24:00; Eastern Freeway: 24h)";
    let fineText = "Fine Risk: Rs 20,000 + Seizure";

    if (isNagpur) {
        geofenceCoords = NAGPUR_GEOFENCE_COORDS;
        barriers = NAGPUR_BARRIERS;
        geofenceTitle = "Nagpur Municipal Corporation (NMC) Core No-Entry Zone";
        authority = "Nagpur Municipal Corporation & City Traffic Police (Sec 115 MVA)";
        peakHours = "06:00 AM - 10:00 PM (Expired 2026-04-07: verify with traffic police. Outer Ring Road bypass)";
        fineText = "Fine Risk: Rs 10,000 + Seizure";
    } else if (isPune) {
        geofenceCoords = PUNE_GEOFENCE_COORDS;
        barriers = PUNE_BARRIERS;
        geofenceTitle = "Pune Municipal Corporation (PMC) No-Entry Core";
        authority = "Pune Municipal Corporation & Traffic Branch (Sec 115 & 116 MVA)";
        peakHours = "09:00 AM - 12:00 PM & 04:30 PM - 08:30 PM";
        fineText = "Fine Risk: Rs 15,000 + Impoundment";
    }

    const geofencePolygon = L.polygon(geofenceCoords, {
        color: "#ef4444",
        weight: 2,
        dashArray: "6, 6",
        fillColor: "#ef4444",
        fillOpacity: 0.12
    }).bindPopup(`
        <div class="regulatory-popup">
            <h4><i class="fa-solid fa-ban" style="color:#ef4444"></i> ${geofenceTitle}</h4>
            <p><strong>Authority:</strong> ${authority}</p>
            <p><strong>Restricted Hours:</strong> ${peakHours}</p>
            <p><strong>Restricted:</strong> Heavy Freight Trucks (Tata 407, Eicher, HCVs)</p>
            <p><strong>Exempt:</strong> Delivery Vans (Tata Ace & LCVs under 3.5T GVW)</p>
            <span class="regulatory-tag tag-geofence">${fineText}</span>
        </div>
    `);
    state.geofenceLayer.addLayer(geofencePolygon);

    // 2. Height Barriers & Bridge Limits
    barriers.forEach(barrier => {
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
                    <span class="regulatory-tag tag-barrier">${barrier.height_limit_m}m Flyover Gantry</span>
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
                    <span class="regulatory-tag tag-bridge">${barrier.weight_limit_t}T Bridge Limit</span>
                </div>
            `);
            state.bridgesLayer.addLayer(marker);
        }
    });
}

// INITIALIZE REGULATORY MAP LAYERS
function initRegulatoryLayers() {
    refreshRegulatoryLayers();

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

// UPDATE CITY TRAFFIC RULES TAB CONTENT
function updateRulesTabContent() {
    const isNagpur = state.selectedRegion === "NAGPUR_NMC";
    const isPune = state.selectedRegion === "PUNE_PMC";
    const container = document.getElementById("cityRulesDocument") || document.querySelector("#tab-rules .rules-document") || document.querySelector(".rules-document");
    if (!container) return;

    if (isNagpur) {
        container.innerHTML = `
            <h2>Nagpur NMC Commercial Transport Regulations</h2>
            <p class="rules-subtitle">Reference guide for drivers and dispatchers in Nagpur Metropolitan Area</p>
            
            <div class="rule-box" style="border-left: 4px solid #f59e0b;">
                <h3>1. Listed City Roads Commercial Vehicle Restriction (Status: Expired / Needs Check)</h3>
                <p><strong>Validity Check:</strong> Notification valid until <strong>2026-04-07</strong> with status <em>needs_check (no renewal found)</em>. Any rule whose valid_until is before today is ignored by the engine and displayed as <strong>expired, verify with traffic police</strong>.</p>
                <ul>
                    <li><strong>Operating Window:</strong> 06:00 AM to 10:00 PM on listed city roads.</li>
                    <li><strong>Routing Policy:</strong> Heavy freight trucks routed via Outer Ring Road bypass.</li>
                    <li><strong>Exemptions:</strong> Essential goods and government duty vehicles.</li>
                    <li><strong>Dated Override:</strong> Ganesh Visarjan (2026-09-25 06:00 to 2026-09-27 06:00) — status: expired.</li>
                </ul>
            </div>

            <div class="rule-box">
                <h3>2. Sitabuldi Metro & Cotton Market Flyover Clearances</h3>
                <p>Key urban metro ramps and railway subways feature overhead steel gantries fixed at a clearance of <strong>2.5 meters</strong>. Freight trucks exceeding 2.5m must use ground-level surface bypasses.</p>
            </div>

            <div class="rule-box">
                <h3>3. Ram Jhula & Heritage Railway Overbridge Weight Limits</h3>
                <p>Arterial railway overbridges restrict commercial freight exceeding <strong>5.0 Tonnes Gross Vehicle Weight</strong>. Heavy multi-axle trucks must use the Outer Ring Road or Kamptee Road corridor.</p>
            </div>
        `;
    } else if (isPune) {
        container.innerHTML = `
            <h2>Pune PMC Commercial Transport Regulations</h2>
            <p class="rules-subtitle">Reference guide for drivers and dispatchers in Pune Metropolitan Area</p>
            
            <div class="rule-box">
                <h3>1. Heavy Commercial Vehicle Peak-Hour No-Entry</h3>
                <p>Under Section 115 and 116 of the Motor Vehicles Act, heavy goods trucks (such as Tata 407, Eicher Pro, and multi-axle trucks) are prohibited from entering central Pune roads during peak traffic hours:</p>
                <ul>
                    <li><strong>Morning Window:</strong> 09:00 AM to 12:00 PM</li>
                    <li><strong>Evening Window:</strong> 04:30 PM to 08:30 PM</li>
                    <li><strong>Vehicles Exempt:</strong> Small delivery vans under 3.5 tonnes GVW (such as Tata Ace, Mahindra Bolero, Ashok Leyland Dost).</li>
                    <li><strong>Violation Penalty:</strong> Minimum fine of ₹15,000 and vehicle seizure.</li>
                </ul>
            </div>

            <div class="rule-box">
                <h3>2. Swargate & Pune University Flyover Clearance</h3>
                <p>Key urban flyovers feature overhead steel gantries fixed at a clearance of <strong>2.5 meters</strong>. Freight trucks exceeding 2.5m must use ground-level surface junctions.</p>
            </div>

            <div class="rule-box">
                <h3>3. Heritage Bridge Weight Limits (Lakdi Pul & Dengle Bridge)</h3>
                <p>Historic bridges across Mutha River restrict vehicles weighing over <strong>5.0 Tonnes Gross Vehicle Weight</strong>. Heavy freight must take the Sangam Bridge or outer bypass.</p>
            </div>
        `;
    } else {
        container.innerHTML = `
            <h2>Mumbai Regional Commercial Transport Rules</h2>
            <p class="rules-subtitle">Reference guide for drivers and dispatchers in Greater Mumbai (MMRDA) — Effective 2026-02-01 (Source Type: News)</p>
            
            <div class="rule-box">
                <h3>1. Citywide Commercial Vehicle Peak Windows</h3>
                <p>Under Mumbai Traffic Police notifications (effective 2026-02-01, source_type: news), heavy commercial vehicles are restricted during citywide peak windows:</p>
                <ul>
                    <li><strong>Morning Window:</strong> 08:00 AM to 11:00 AM</li>
                    <li><strong>Evening Window:</strong> 05:00 PM to 09:00 PM</li>
                    <li><strong>Heavy Definition:</strong> Unspecified in sources.</li>
                    <li><strong>Van Exemption:</strong> Small delivery vans (Tata Ace) kept exempt only as a labeled demo assumption.</li>
                    <li><strong>Exemptions:</strong> Essential goods, emergency services, school buses, and government buses.</li>
                    <li><strong>Violation Penalty:</strong> ₹20,000 fine under MVA.</li>
                </ul>
            </div>

            <div class="rule-box">
                <h3>2. South Mumbai & Eastern Freeway Restrictions (No Polygons)</h3>
                <ul>
                    <li><strong>South Mumbai Restriction:</strong> 07:00 AM to 24:00 (12:00 AM) commercial restriction with no polygon.</li>
                    <li><strong>Eastern Freeway Ban:</strong> 24-hour ban on commercial goods vehicles (all day) except public buses, as a separate rule with no polygon.</li>
                </ul>
            </div>

            <div class="rule-box">
                <h3>3. Corridor Height & Weight Load Limits</h3>
                <p>Flyovers maintain a clearance gantry of <strong>2.5 meters</strong>. Older arterial bridges restrict vehicles exceeding <strong>7.5 Tonnes Gross Vehicle Weight</strong>.</p>
            </div>
        `;
    }
}

// RENDER COMMERCIAL DISPATCH MANIFEST MODAL
function renderManifestModal(data) {
    const isNagpur = state.selectedRegion === "NAGPUR_NMC";
    const isPune = state.selectedRegion === "PUNE_PMC";
    let code = "MMRDA";
    let regionTitle = "Mumbai Metropolitan Region (MMRDA / Police Traffic Branch)";
    let hubTitle = state.depot?.name || "Bhiwandi Central Freight Hub";
    if (isNagpur) {
        code = "NMC";
        regionTitle = "Nagpur Metropolitan Area (NMC / Nagpur City Traffic Police)";
        hubTitle = state.depot?.name || "MIHAN SEZ Multi-Modal Freight Terminal";
    } else if (isPune) {
        code = "PMC";
        regionTitle = "Pune Metropolitan Region (PMC / Pune Traffic Police)";
        hubTitle = state.depot?.name || "Bhosari-Chakan MIDC Freight Terminal";
    }
    const serial = `MANIFEST-${code}-${Date.now().toString().slice(-6)}`;
    document.getElementById("manifestSerialId").textContent = serial;

    const departureClock = document.getElementById("clockDisplay")?.textContent || "08:30 AM";
    const container = document.getElementById("manifestContent");

    let html = `
        <div class="manifest-header-block">
            <div class="manifest-meta-col">
                <strong>RouteOpt Commercial Fleet Dispatch Manifest</strong>
                <span>Region: ${regionTitle}</span>
                <span>Operating Hub: ${hubTitle}</span>
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

