# RouteOpt Backend (FastAPI Integration API)

This is the FastAPI backend for **RouteOpt**, a multi-stop delivery route optimizer. It connects the OSRM Routing Machine and Google OR-Tools solvers to retrieve optimal stop visit sequences, total travel distance, durations, and routing polylines.

---

## 🛠️ Local Python Setup (Without Docker)

### 1. Prerequisites
Ensure you have **Python 3.11+** installed.

### 2. Setup Virtual Environment & Install Dependencies
Run the following commands in the root directory:
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install package dependencies
pip install -r backend/requirements.txt
```

### 3. Running Automated Tests
To run the test suite and verify endpoints:
```bash
python -m pytest -v
```

### 4. Running the Development Server
Start the local FastAPI development server:
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
*   **API documentation**: Accessible at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (Swagger UI).
*   **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🐳 Docker Deployment Setup

### 1. Prerequisites
*   Docker & Docker Compose installed.
*   India map data downloaded and preprocessed in the `./data/` folder (run by Member 1).

### 2. Run the Stack
To build the API container and start both the OSRM server and the FastAPI backend together, run the following in the project root:
```bash
docker compose up --build
```
The FastAPI backend will automatically resolve OSRM at `http://osrm:5000` via the internal Docker network.

---

## 🛰️ API Endpoints

### 1. GET `/health`
*   **Description**: Verify the backend is up and running.
*   **Response (`200 OK`)**:
    ```json
    {"status": "OK"}
    ```

### 2. POST `/optimize`
*   **Description**: Find the optimal stop sequence and polyline.
*   **Request JSON**:
    ```json
    {
      "depot": [18.5204, 73.8567],
      "stops": [
        [18.5304, 73.8667],
        [18.5404, 73.8767]
      ]
    }
    ```
*   **Response JSON**:
    ```json
    {
      "order": [0, 1, 2, 0],
      "distance_m": 70710.0,
      "duration_s": 5656.8,
      "polyline": "_p~iF~ps|U_ulLnnqC_mqNvxq@"
    }
    ```
