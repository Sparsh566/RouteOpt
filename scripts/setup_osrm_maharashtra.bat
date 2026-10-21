@echo off
REM ==============================================================================
REM RouteOpt: Local OSRM Backend Setup Script for Windows (Docker required)
REM ==============================================================================

set DATA_DIR=%cd%\data\osrm
set PBF_FILE=western-zone-latest.osm.pbf
set OSM_URL=https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf
set OSRM_IMAGE=ghcr.io/project-osrm/osrm-backend:latest

echo === 1. Creating OSRM Data Directory ===
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
cd /d "%DATA_DIR%"

if not exist "%PBF_FILE%" (
    echo === 2. Downloading Western Zone OSM Extract ===
    curl -L -o "%PBF_FILE%" "%OSM_URL%"
) else (
    echo === 2. %PBF_FILE% already exists. Skipping download. ===
)

echo === 3. Extracting Road Network with car profile ===
docker run -t -v "%DATA_DIR%:/data" %OSRM_IMAGE% osrm-extract -p /opt/car.lua /data/%PBF_FILE%

echo === 4. Partitioning MLD Graph ===
docker run -t -v "%DATA_DIR%:/data" %OSRM_IMAGE% osrm-partition /data/western-zone-latest.osrm

echo === 5. Customizing Cells ===
docker run -t -v "%DATA_DIR%:/data" %OSRM_IMAGE% osrm-customize /data/western-zone-latest.osrm

echo === 6. Launching OSRM Container on Port 5000 ===
docker run -d --name routeopt-osrm -p 5000:5000 -v "%DATA_DIR%:/data" %OSRM_IMAGE% osrm-routed --algorithm mld /data/western-zone-latest.osrm

echo === Local OSRM is live at http://localhost:5000 ===
