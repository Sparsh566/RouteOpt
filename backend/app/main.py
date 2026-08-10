from fastapi import FastAPI
from backend.app.config import settings
from backend.app.controllers.optimize import router as optimize_router
from backend.app.utils import ExternalServiceException, external_service_exception_handler

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend routing API to solve VRP/TSP with OSRM and OR-Tools.",
    version="1.0.0"
)

# Register routers
app.include_router(optimize_router, tags=["Optimization"])

# Register custom exception handlers
app.add_exception_handler(ExternalServiceException, external_service_exception_handler)

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "OK"}
