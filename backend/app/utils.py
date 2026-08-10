from fastapi import Request
from fastapi.responses import JSONResponse

class ExternalServiceException(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message

async def external_service_exception_handler(request: Request, exc: ExternalServiceException):
    return JSONResponse(
        status_code=502,
        content={
            "detail": f"Bad Gateway: Error communicating with external service '{exc.name}'.",
            "message": exc.message
        }
    )
