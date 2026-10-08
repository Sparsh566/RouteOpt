import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.app.config import settings
from backend.app.controllers.optimize import router as optimize_router
from backend.app.controllers.simulate import router as simulate_router
from backend.app.utils import ExternalServiceException, external_service_exception_handler

app = FastAPI(
    title=settings.APP_NAME,
    description="RouteOpt: Commercial Fleet (LCVs & Trucks) Route Optimization with Regional Road Guidelines and AI 'What-If' Simulation.",
    version="2.0.0"
)

# Enable CORS for cross-origin frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(optimize_router, prefix="/api")
app.include_router(simulate_router, prefix="/api")

# Register custom exception handlers
app.add_exception_handler(ExternalServiceException, external_service_exception_handler)

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "OK",
        "app": settings.APP_NAME,
        "ai_enabled": bool(settings.GROK_API_KEY or settings.GROQ_API_KEY),
        "osrm_endpoint": settings.OSRM_URL
    }

# Mount frontend directory for seamless local and production hosting
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
