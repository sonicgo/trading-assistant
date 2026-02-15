from fastapi import FastAPI

app = FastAPI(title="Trading Assistant API")

@app.get("/health")
def health_check():
    return {"status": "ok", "phase": "0"}
