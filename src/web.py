import os
from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "RahYar Bot"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


def run():
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
