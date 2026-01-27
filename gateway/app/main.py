from fastapi import Depends, FastAPI

from gateway.app.db.base import Base
from gateway.app.db.session import get_engine
from gateway.app.db import models  # noqa: F401 - import to register models
from gateway.app.middleware.auth import require_api_key

app = FastAPI(title="TeachProxy Gateway")

engine = get_engine()
Base.metadata.create_all(engine)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/chat/completions")
def chat_completions(_key=Depends(require_api_key)):
    return {"error": "not_implemented"}
