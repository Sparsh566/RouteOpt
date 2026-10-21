# Local OSRM Road Data Setup Guide

RouteOpt provides two modes for computing distance and duration matrices between waypoints:
1. **Live OSRM Road Graph (`is_real_road_data: true`)**: Real road routing computed over physical OpenStreetMap road networks using Open Source Routing Machine (OSRM).
2. **High-Fidelity Detour Model (`is_real_road_data: false`)**: Deterministic crow-fly distance multiplied by an empirical urban detour coefficient ($1.35\times$) with standard commercial city speed ($30\text{ km/h} \approx 8.33\text{ m/s}$). Every response explicitly indicates `is_real_road_data` to ensure honesty of scientific claims.

---

## 1. Quick Local OSRM Setup with Docker

### Prerequisites
- Docker Desktop or Docker Engine installed and running.
- ~1.5 GB free disk space for the Western Zone (Maharashtra) extract.

### Automated Setup
On Linux/macOS:
```bash
chmod +x scripts/setup_osrm_maharashtra.sh
./scripts/setup_osrm_maharashtra.sh
```

On Windows:
```cmd
scripts\setup_osrm_maharashtra.bat
```

### Manual Step-by-Step Instructions
1. **Download the OpenStreetMap PBF extract:**
   ```bash
   mkdir -p data/osrm && cd data/osrm
   curl -L -O https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf
   ```

2. **Extract with car routing profile:**
   ```bash
   docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend:latest \
       osrm-extract -p /opt/car.lua /data/western-zone-latest.osm.pbf
   ```

3. **Partition and customize MLD cells:**
   ```bash
   docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend:latest \
       osrm-partition /data/western-zone-latest.osrm

   docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend:latest \
       osrm-customize /data/western-zone-latest.osrm
   ```

4. **Run OSRM Routed Server on Port 5000:**
   ```bash
   docker run -d --name routeopt-osrm -p 5000:5000 -v "${PWD}:/data" \
       ghcr.io/project-osrm/osrm-backend:latest \
       osrm-routed --algorithm mld /data/western-zone-latest.osrm
   ```

5. **Verify Health:**
   ```bash
   curl "http://localhost:5000/route/v1/driving/72.9565,19.1726;72.8478,19.0178?overview=false"
   ```

Once running, RouteOpt automatically queries `http://localhost:5000` and reports `is_real_road_data: true`.
