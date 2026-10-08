# RouteOpt: Commercial Fleet Route Optimization and AI Dispatch Simulator

RouteOpt is an intelligent transport management system designed for Indian urban freight operations. It optimizes multi-vehicle commercial logistics fleets (Delivery Vans like Tata Ace and Freight Trucks like Tata 407) under municipal road guidelines, peak-hour entry bans, low-clearance flyover restrictions, and delivery time windows. It includes an interactive Leaflet dispatch interface with live vehicle movement animation and an AI-driven "What-If" scenario simulator powered by Groq.

---

## Key Features

1. **Multi-Vehicle CVRPTW Solver:**
   - Solves Capacitated Vehicle Routing Problem with Time Windows using Google OR-Tools.
   - Differentiates vehicle classes:
     - **Delivery Van (LCV - Tata Ace / Dost):** 1,200 kg payload, 1.9 m height clearance, exempt from urban peak-hour bans.
     - **Freight Truck (MCV/HCV - Tata 407 / Eicher):** 4,500 kg payload, 3.1 m height, subject to peak bans and flyover limits.
   - Embedded greedy heuristic fallback for resilient deployment on serverless platforms.

2. **Regional Road Guidelines Engine:**
   - Models municipal traffic notifications (such as Mumbai MMRDA and Pune PMC):
     - **Morning Peak No-Entry Ban:** 08:00 AM to 11:30 AM for heavy goods vehicles.
     - **Evening Peak No-Entry Ban:** 05:00 PM to 09:30 PM for heavy goods vehicles.
     - **Flyover Height Barriers:** 2.5-meter clearance gantries redirecting trucks to surface roads.
     - **Bridge GVW Limits:** 7.5-tonne gross vehicle weight limits on older arterial spans.
     - Penalty calculation (Rs 20,000 fine risk under Section 115 and 116 of the Motor Vehicles Act).

3. **AI What-If Disruption Simulator:**
   - Evaluates unexpected road conditions (toll delays, weather disruptions, emergency drop additions, and vehicle breakdowns).
   - Powered by Groq LLM (gpt-oss-120b) to provide 3-sentence operational guidance for dispatchers and drivers.
   - Supports both curated preset scenarios and custom free-text driver problem descriptions.

4. **Live Driver Route Movement Simulation:**
   - Interactive Leaflet map visualizing vehicle transit along road polylines.
   - Real-time vehicle marker animations with speed toggles (1x, 2x, 4x).
   - Live status indicator displaying current route legs, drop points, and cargo weights.

---

## System Architecture

```
                  +-----------------------------------+
                  |         Dispatch Web UI           |
                  |   (Leaflet Map + Logistics Theme) |
                  +-----------------+-----------------+
                                    |
                                    v
                     +--------------+--------------+
                     |       FastAPI Backend       |
                     |  (Local or Vercel Serverless)|
                     +--------------+--------------+
                                    |
         +--------------------------+--------------------------+
         |                          |                          |
         v                          v                          v
+-----------------+        +-----------------+        +-----------------+
|  CVRPTW Engine  |        | Regulation Base |        |  AI Simulation  |
| (OR-Tools /     |        | (MMRDA & Police |        | (Groq Fast LLM  |
|  Greedy Solver) |        |  Traffic Rules) |        |  gpt-oss-120b)  |
+-----------------+        +-----------------+        +-----------------+
         |
         v
+-----------------+
|  OSRM / Haversine|
| Distance Matrix |
+-----------------+
```

---

## Directory Structure

```
RouteOpt/
├── api/
│   ├── index.py                  # Vercel serverless ASGI entrypoint
│   └── requirements.txt          # API dependencies for Vercel
├── backend/
│   ├── app/
│   │   ├── controllers/
│   │   │   ├── optimize.py       # Route optimization controller
│   │   │   └── simulate.py       # AI simulation and guidelines controller
│   │   ├── models/
│   │   │   ├── fleet_v2.py       # Pydantic schemas for fleet and CVRPTW
│   │   │   └── simulation_v3.py  # Simulation request and response schemas
│   │   ├── services/
│   │   │   ├── ai_simulation_engine.py # Groq LLM advisory service
│   │   │   ├── cvrptw_solver.py  # OR-Tools and greedy CVRPTW solver
│   │   │   ├── osrm_service.py   # Distance and duration matrix client
│   │   │   ├── regulation_engine.py # Road rules and fine calculation
│   │   │   └── traffic_engine.py # Congestion factor calculation
│   │   ├── config.py             # Environment configuration
│   │   └── main.py               # FastAPI application setup
│   ├── tests/
│   │   └── test_v2_v3.py         # Pytest verification suite
│   └── requirements.txt          # Backend dependencies
├── frontend/
│   ├── app.js                    # Dispatch client, map logic, and animations
│   ├── index.html                # Driver/dispatcher web interface
│   └── style.css                 # Solid dark-slate logistics styling
├── plan.md                       # Strategic system architecture blueprint
├── implementation.md             # Technical implementation reference
├── requirements.txt              # Root dependencies for cloud deployment
├── run.py                        # Local development runner
└── vercel.json                   # Vercel cloud deployment routing rules
```

---

## API Reference

### 1. Health Check
* **GET** `/health`
* **Response:**
  ```json
  {
    "status": "OK",
    "app": "RouteOpt Commercial Fleet & AI Simulation Engine",
    "ai_enabled": true,
    "osrm_endpoint": "http://localhost:5000"
  }
  ```

### 2. Fleet Route Optimization
* **POST** `/api/optimize`
* **Description:** Generates optimal multi-vehicle routes respecting capacities, time windows, and municipal entry bans.
* **Payload Example:**
  ```json
  {
    "depot": {
      "depot_id": "DEPOT-BHIWANDI",
      "name": "Bhiwandi Central Freight Hub",
      "lat": 19.2967,
      "lon": 73.0631,
      "operating_hours_sec": 43200
    },
    "stops": [
      {
        "stop_id": "STOP-01",
        "name": "Mulund Commercial Checkpost",
        "lat": 19.1726,
        "lon": 72.9565,
        "demand_kg": 450,
        "time_window_start_sec": 0,
        "time_window_end_sec": 36000,
        "service_duration_sec": 600,
        "is_in_restricted_urban_core": true
      }
    ],
    "fleet": [
      {
        "vehicle_id": "VAN-01",
        "name": "Tata Ace Van 1",
        "vehicle_class": "van",
        "gross_vehicle_weight_tonnes": 2.2,
        "height_meters": 1.9,
        "payload_capacity_kg": 1200.0,
        "fixed_dispatch_cost": 250.0,
        "running_cost_per_km": 12.0,
        "color_hex": "#0284c7"
      }
    ],
    "departure_time_iso": "2026-10-09T08:30:00+05:30",
    "region": "MUMBAI_MMRDA",
    "apply_traffic_congestion": true,
    "enforce_government_guidelines": true
  }
  ```

### 3. Scenario Simulation
* **POST** `/api/simulate`
* **Description:** Runs an operational disruption simulation using preset scenarios or user-entered custom situations.
* **Payload Example (Custom Problem):**
  ```json
  {
    "scenario_type": "CUSTOM_SITUATION",
    "custom_situation_text": "Truck is delayed at Dadar market for 45 mins due to rain. Will it miss the 5:00 PM entry ban?",
    "depot": { ... },
    "fleet": [ ... ],
    "stops": [ ... ],
    "departure_time_iso": "2026-10-09T08:30:00+05:30",
    "parameters": {}
  }
  ```

### 4. Regional Guidelines
* **GET** `/api/guidelines?region=MUMBAI_MMRDA`
* **Description:** Retrieves municipal truck restriction windows, height limits, and legal citations.

---

## Getting Started Locally

### 1. Clone Repository
```bash
git clone https://github.com/Sparsh566/RouteOpt.git
cd RouteOpt
```

### 2. Set Up Virtual Environment
```bash
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_api_key_here
OSRM_URL=http://localhost:5000
DEFAULT_REGION=MUMBAI_MMRDA
```

### 5. Run the Application
```bash
python run.py
```
Open your browser at `http://127.0.0.1:8000`. API documentation is available at `http://127.0.0.1:8000/docs`.

### 6. Run Test Suite
```bash
python -m pytest backend/tests/test_v2_v3.py -v
```

---

## Deployment on Vercel

RouteOpt is configured for zero-config Vercel deployment:

1. Import repository `Sparsh566/RouteOpt` on [Vercel](https://vercel.com/new).
2. Ensure the deployment branch is set to `main`.
3. Add the following environment variable under Project Settings:
   - `GROQ_API_KEY`: Your Groq API key
4. Click **Deploy**. Vercel will build the serverless Python functions and deploy the frontend static interface automatically.

---

## License

This project is developed for academic and engineering demonstrations of commercial logistics optimization.