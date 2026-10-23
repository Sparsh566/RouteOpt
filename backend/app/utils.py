from datetime import datetime, timedelta, timezone

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

def parse_departure_datetime(departure_iso: str | None) -> tuple[datetime, int]:
    """
    Parses departure ISO string into timezone-aware datetime (defaulting to IST, UTC+05:30)
    and returns (datetime_obj, seconds_since_midnight).
    """
    ist = timezone(timedelta(hours=5, minutes=30))
    if not departure_iso:
        dt = datetime.now(ist).replace(hour=8, minute=30, second=0, microsecond=0)
    else:
        try:
            dt = datetime.fromisoformat(departure_iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ist)
        except Exception:
            dt = datetime.now(ist).replace(hour=8, minute=30, second=0, microsecond=0)
    sec_since_midnight = dt.hour * 3600 + dt.minute * 60 + dt.second
    return dt, sec_since_midnight

