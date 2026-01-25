from fastapi import Header, HTTPException, status
from typing import Optional


def get_current_user(x_user_id: Optional[str] = Header(None, alias="X-User-Id")) -> str:
    # In a real environment, this validates a JWT.
    # For backward compatibility with legacy endpoints, we allow None but controllers may enforce it.
    if not x_user_id:
        # Fallback to system for legacy support if needed, or raise.
        return "system_user"
    return x_user_id


def require_current_user(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication credentials")
    return x_user_id
