from __future__ import annotations

import base64
import secrets

from fastapi import Depends, Header, HTTPException, Request, status

from app import config


def _check_basic_auth(auth_header: str) -> bool:
    if not auth_header.startswith("Basic "):
        return False
    token = auth_header[6:].strip()
    try:
        decoded = base64.b64decode(token).decode("utf-8")
    except Exception:
        return False
    if ":" not in decoded:
        return False
    username, password = decoded.split(":", 1)
    return secrets.compare_digest(username, config.API_ACCESS_USERNAME) and secrets.compare_digest(
        password, config.API_ACCESS_PASSWORD
    )


def _auth_enabled() -> bool:
    return bool(config.API_ACCESS_USERNAME and config.API_ACCESS_PASSWORD)


async def require_basic_auth(request: Request) -> None:
    # Allow trusted app-to-app calls with internal key (used by frontend runtime).
    if config.INTERNAL_API_KEY:
        x_app_key = request.headers.get("X-App-Key", "")
        if secrets.compare_digest(x_app_key, config.INTERNAL_API_KEY):
            return
    if not _auth_enabled():
        return
    auth_header = request.headers.get("Authorization", "")
    if _check_basic_auth(auth_header):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_internal_api_key(x_app_key: str = Header(default="", alias="X-App-Key")) -> None:
    if not config.INTERNAL_API_KEY:
        return
    if secrets.compare_digest(x_app_key, config.INTERNAL_API_KEY):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


InternalApiKeyDep = Depends(require_internal_api_key)
