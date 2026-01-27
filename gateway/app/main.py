from fastapi import FastAPI

from gateway.app.api.chat import router as chat_router
from gateway.app.db.base import Base
from gateway.app.db.session import get_engine
from gateway.app.db import models  # noqa: F401 - import to register models

app = FastAPI(title="TeachProxy Gateway")
app.include_router(chat_router)

engine = get_engine()
Base.metadata.create_all(engine)


@app.get("/health")
def health():
    return {"status": "ok"}
