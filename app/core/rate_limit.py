from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.security import decode_access_token, settings

DEFAULT_LIMIT = "90/minute"
AUTH_LIMIT = "20/minute"
REFRESH_LIMIT = "10/minute"

def _get_client_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.removeprefix("Bearer ").strip()
        sub = decode_access_token(token)
        if sub:
            return f"user:{sub}"
    return get_remote_address(request)


limiter = Limiter(
    key_func=_get_client_key,
    default_limits=[DEFAULT_LIMIT],
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
)
