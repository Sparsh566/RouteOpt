# RouteOpt: Commercial Fleet Route Optimization and AI Dispatch Simulator

RouteOpt is an intelligent transport management and route optimization system designed for commercial freight operations in Indian metropolitan corridors. It optimizes heterogeneous fleets—small delivery vans (e.g., Tata Ace / Ashok Leyland Dost) and freight trucks (e.g., Tata 407 / BharatBenz)—under municipal traffic regulations, peak-hour entry bans, low-clearance flyover restrictions, and customer delivery time windows.

The system combines Google OR-Tools CVRPTW mathematical optimization, an independent post-solution route validator, deterministic simulation fallbacks, and an interactive Leaflet dispatch interface with live vehicle tracking and a Fleet Manager dashboard.

---

## Formal Mathematical Model

RouteOpt models urban commercial logistics as a **Capacitated Vehicle Routing Problem with Time Windows and Regional Regulatory Constraints (CVRPTW-RC)**.

### Sets and Parameters

- $\mathcal{V} = \{0, 1, \dots, n\}$: Nodes, where $0$ is the central depot and $\mathcal{C} = \{1, \dots, n\}$ are customer delivery stops.
- $\mathcal{K}$: Set of available commercial vehicles in the fleet.
- $q_i$: Demand payload at stop $i \in \mathcal{C}$ (kg).
- $[e_i, l_i]$: Delivery time window for stop $i$ (seconds from midnight).
- $s_i$: Service duration / unloading dwell time at stop $i$ (seconds).
- $Q_k$: Payload capacity of vehicle $k \in \mathcal{K}$ (kg).
- $F_k$: Fixed vehicle dispatch cost (₹).
- $c_k$: Variable operational cost per kilometer (₹/km).
- $d_{ij}$: Distance from node $i$ to node $j$ (km).
- $\tau_{ij}$: Travel duration from node $i$ to node $j$ under active traffic congestion (seconds).
- $H$: Maximum permissible shift operating horizon (seconds).
- $P_i$: Penalty cost for dropping unserved customer stop $i$ (₹2,500).
- $\mathcal{W}_{\text{ban}} = \bigcup [B_m^{\text{start}}, B_m^{\text{end}}]$: Municipal peak-hour no-entry windows for heavy freight vehicles.
- $\mathcal{C}_{\text{core}} \subseteq \mathcal{C}$: Delivery stops located within municipal restricted urban cores.
- $\mathcal{K}_{\text{truck}} \subseteq \mathcal{K}$: Heavy freight vehicles subject to peak no-entry and height barriers.

### Decision Variables

- $x_{ijk} \in \{0, 1\}$: $1$ if vehicle $k$ traverses arc $(i, j)$, $0$ otherwise.
- $u_k \in \{0, 1\}$: $1$ if vehicle $k$ is utilized in the dispatch plan, $0$ otherwise.
- $t_{ik} \ge 0$: Arrival time of vehicle $k$ at node $i$.
- $y_i \in \{0, 1\}$: $1$ if stop $i$ is dropped (unserved), $0$ if fulfilled.

### Objective Function

$$\min \quad \sum_{k \in \mathcal{K}} F_k \cdot u_k + \sum_{k \in \mathcal{K}} c_k \sum_{i \in \mathcal{V}} \sum_{j \in \mathcal{V}} d_{ij} x_{ijk} + \sum_{i \in \mathcal{C}} P_i \cdot y_i$$

### Constraints

1. **Stop Fulfillment or Explicit Drop:**
   $$\sum_{k \in \mathcal{K}} \sum_{j \in \mathcal{V}, j \ne i} x_{ijk} + y_i = 1, \quad \forall i \in \mathcal{C}$$

2. **Flow Conservation:**
   $$\sum_{j \in \mathcal{V}, j \ne p} x_{jpk} - \sum_{j \in \mathcal{V}, j \ne p} x_{pjk} = 0, \quad \forall p \in \mathcal{C}, \forall k \in \mathcal{K}$$
   $$\sum_{j \in \mathcal{C}} x_{0jk} = u_k \le 1, \quad \sum_{i \in \mathcal{C}} x_{i0k} = u_k \le 1, \quad \forall k \in \mathcal{K}$$

3. **Vehicle Payload Capacity:**
   $$\sum_{i \in \mathcal{C}} q_i \sum_{j \in \mathcal{V}} x_{ijk} \le Q_k \cdot u_k, \quad \forall k \in \mathcal{K}$$

4. **Time Windows and Arrival Propagation:**
   $$t_{ik} + s_i + \tau_{ij} - M(1 - x_{ijk}) \le t_{jk}, \quad \forall i \in \mathcal{V}, j \in \mathcal{C}, \forall k \in \mathcal{K}$$
   $$e_i \le t_{ik} \le l_i, \quad \forall i \in \mathcal{C}, \forall k \in \mathcal{K}$$

5. **Depot Operating Shift Horizon:**
   $$t_{0k}^{\text{return}} - t_{0k}^{\text{depart}} \le H, \quad \forall k \in \mathcal{K}$$

6. **Municipal Peak-Hour Truck Restriction:**
   $$t_{ik} \notin \mathcal{W}_{\text{ban}}, \quad \forall i \in \mathcal{C}_{\text{core}}, \forall k \in \mathcal{K}_{\text{truck}}$$

7. **Overhead Height Gantry and Bridge GVW Clearances:**
   Arcs spanning restricted flyovers ($h_k > H_{\text{flyover}}$) or weight-restricted bridges ($\text{GVW}_k > W_{\text{bridge}}$) are assigned infinite impedance in the distance matrix.

---

## System Architecture

```
                       +---------------------------------------+
                       |           Dispatch Web HUD            |
                       | (Leaflet Map, Manager Dashboard, HUD) |
                       +-------------------+-------------------+
                                           |
                                  HTTP REST / JSON
                                           |
                                           v
                       +---------------------------------------+
                       |           FastAPI Application         |
                       |       (/api/optimize, /api/simulate)  |
                       +-------------------+-------------------+
                                           |
         +---------------------------------+---------------------------------+
         |                                 |                                 |
         v                                 v                                 v
+------------------+             +-------------------+             +-------------------+
|  CVRPTW Solver   |             |  Regulation Base  |             |  AI Simulator     |
| (Google OR-Tools |             |  (MMRDA, PMC,     |             | (Strict Grounding |
| / Greedy Backup) |             |   NMC Rules DB)   |             | & Rule Fallback)  |
+--------+---------+             +---------+---------+             +-------------------+
         |                                 |
         +----------------+----------------+
                          |
                          v
               +----------------------+
               |    RouteValidator    |
               | (Independent Audit of|
               | 9 Constraint Classes)|
               +----------------------+
```

---

## Directory Structure

```
RouteOpt/
├── backend/
│   ├── app/
│   │   ├── controllers/
│   │   │   ├── optimize.py          # /api/optimize endpoint handler
│   │   │   └── simulate.py          # /api/simulate disruption sandbox
│   │   ├── data/
│   │   │   └── regulations.json     # Regional regulations database
│   │   ├── models/
│   │   │   ├── fleet_v2.py          # Pydantic models for fleet and CVRPTW
│   │   │   └── simulation_v3.py     # Disruption request/response schemas
│   │   ├── services/
│   │   │   ├── ai_simulation_engine.py # Disruption analysis engine
│   │   │   ├── cvrptw_solver.py     # OR-Tools & greedy fallback solver
│   │   │   ├── osrm_service.py      # Live OSRM / Haversine winding service
│   │   │   ├── regulation_engine.py # RegionalRegulationEngine
│   │   │   ├── traffic_engine.py    # Congestion multiplier service
│   │   │   └── validator.py         # Independent RouteValidator
│   │   ├── config.py                # App configuration & settings
│   │   └── main.py                  # FastAPI app entrypoint
│   └── tests/                       # Automated pytest verification suite
├── benchmarks/
│   ├── data/solomon/                # Standard Solomon benchmark files (.txt)
│   ├── instances/                   # Synthetic benchmark instances (.json)
│   ├── generator.py                 # Reproducible instance generator
│   ├── run.py                       # Unified CLI benchmark harness
│   └── solomon_validator.py         # Solomon loader & optimality gap validator
├── frontend/
│   ├── app.js                       # Map rendering, UI controls, HUD
│   ├── index.html                   # Single-page dispatch application
│   └── style.css                    # Dark logistics theme CSS
├── results/                         # Generated benchmark CSVs and plots
├── .github/workflows/test.yml       # CI workflow (ruff, mypy, pytest)
├── pyproject.toml                   # Ruff and MyPy tooling configuration
├── requirements.txt                 # Production dependencies
└── requirements-dev.txt             # Development & testing dependencies
```

---

## Step-by-Step Setup Instructions

### Prerequisites
- Python 3.11 or higher
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/Sparsh566/RouteOpt.git
cd RouteOpt
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements-dev.txt
```

### 4. Configure Environment Variables
```bash
# Copy example configuration
cp .env.example .env
```
*(Optional: Provide `GROQ_API_KEY` in `.env` for AI advisory text. If omitted, RouteOpt uses its deterministic dispatch rule fallback automatically).*

### 5. Run Backend Server
```bash
python run.py
```
The server will start at `http://127.0.0.1:8000`. Navigate to `http://127.0.0.1:8000` in your browser to access the Leaflet Dispatch UI.

---

## Benchmark Reproduction Guide

### 1. Standard Solomon CVRPTW Validation
Evaluates RouteOpt's OR-Tools engine on standard literature instances (C101, R101, RC101) and reports the optimality gap against Best-Known Solutions (BKS):
```bash
python benchmarks/solomon_validator.py
```

### 2. Synthetic Instance Generation
Generates reproducible Indian urban logistics scenarios with configurable seed, stop count, region, and fleet mix:
```bash
python benchmarks/generator.py --seed 42 --stops 25 --region MUMBAI_MMRDA --fleet-mix mixed
```

### 3. Policy & Solver Benchmark Harness
Runs multi-policy comparison across Ban-Ignorant Trucks (Policy A), Ban-Aware Trucks (Policy B), and Mixed Fleet (Policy C) with OR-Tools vs. Greedy solver:
```bash
python benchmarks/run.py --runs 5 --out results/
```
Outputs generated:
- `results/benchmark_summary.csv`: Summary table with mean and std-dev metrics.
- `results/policy_comparison.png`: Cost vs. unserved stops chart across policies.
- `results/solver_comparison.png`: Runtime and cost trade-off between OR-Tools and Greedy fallback.

---

## Automated Verification Suite

Run automated linting, type-checking, and unit tests:
```bash
# Code style and lint check
ruff check backend/

# Strict type checking
mypy backend/

# Unit & regression test suite
pytest -v
```