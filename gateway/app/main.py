from fastapi import FastAPI

app = FastAPI(title="TeachProxy Gateway")


@app.get("/health")
def health():
    return {"status": "ok"}
