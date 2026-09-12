from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {
        "status": "ok",
        "service": "RahYar Bot"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
