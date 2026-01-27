from fastapi import HTTPException, Request


def get_bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth.replace("Bearer ", "", 1).strip()


def require_api_key(request: Request):
    token = get_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing API key")
    return token
