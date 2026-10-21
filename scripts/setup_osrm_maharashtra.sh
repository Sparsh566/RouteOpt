#!/usr/bin/env bash
# ==============================================================================
# RouteOpt: Local OSRM Backend Setup Script (Maharashtra OSM Extract)
# Downloads official Geofabrik OpenStreetMap extract and precomputes MLD graph.
# ==============================================================================

set -euo pipefail

DATA_DIR="${PWD}/data/osrm"
OSM_URL="https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf"
PBF_FILE="western-zone-latest.osm.pbf"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:latest"

echo "=== 1. Creating OSRM Data Directory at ${DATA_DIR} ==="
mkdir -p "${DATA_DIR}"
cd "${DATA_DIR}"

if [ ! -f "${PBF_FILE}" ]; then
    echo "=== 2. Downloading Western Zone (Maharashtra) OSM Extract ==="
    curl -L -o "${PBF_FILE}" "${OSM_URL}"
else
    echo "=== 2. ${PBF_FILE} already exists. Skipping download. ==="
fi

echo "=== 3. Extracting Road Network with car profile ==="
docker run -t -v "${DATA_DIR}:/data" "${OSRM_IMAGE}" osrm-extract -p /opt/car.lua "/data/${PBF_FILE}"

echo "=== 4. Partitioning MLD Graph ==="
docker run -t -v "${DATA_DIR}:/data" "${OSRM_IMAGE}" osrm-partition "/data/${PBF_FILE%.osm.pbf}.osrm"

echo "=== 5. Customizing Cells ==="
docker run -t -v "${DATA_DIR}:/data" "${OSRM_IMAGE}" osrm-customize "/data/${PBF_FILE%.osm.pbf}.osrm"

echo "=== 6. Launching OSRM Routed Container on Port 5000 ==="
docker run -d --name routeopt-osrm -p 5000:5000 -v "${DATA_DIR}:/data" "${OSRM_IMAGE}" osrm-routed --algorithm mld "/data/${PBF_FILE%.osm.pbf}.osrm"

echo "=== Local OSRM is live at http://localhost:5000 ==="
